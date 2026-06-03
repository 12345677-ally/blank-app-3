import streamlit as st
import time
from datetime import datetime
import json
import io
import os

# --- 外部ライブラリのインポート ---
try:
    import PyPDF2
    from openai import OpenAI
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

# --- ページ設定 ---
st.set_page_config(page_title="AcademiaStream AI", layout="wide", page_icon="🎓")

# --- セッションステートの初期化 ---
if 'app_mode' not in st.session_state: st.session_state.app_mode = 'LEARN'
if 'phase' not in st.session_state: st.session_state.phase = 'UPLOAD'
if 'user_answers' not in st.session_state: st.session_state.user_answers = {}
if 'current_topic' not in st.session_state: st.session_state.current_topic = ""
if 'notes_history' not in st.session_state: st.session_state.notes_history = []
if 'test_history' not in st.session_state: st.session_state.test_history = []
if 'generated_notes' not in st.session_state: st.session_state.generated_notes = None
if 'generated_test' not in st.session_state: st.session_state.generated_test = None

# --- GitHub Models AIの設定 (自動認識) ---
# Codespaces環境には最初から 'GITHUB_TOKEN' という環境変数が隠されています
github_token = os.environ.get("GITHUB_TOKEN")

if github_token:
    # GitHubの無料AIサーバーに接続
    ai_client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=github_token,
    )
else:
    ai_client = None

# --- サイドバー ---
with st.sidebar:
    st.title("🎓 メニュー")
    if st.button("📝 学習を始める", use_container_width=True, type="primary" if st.session_state.app_mode == 'LEARN' else "secondary"):
        st.session_state.app_mode = 'LEARN'
        st.rerun()
    if st.button("📚 学習ノート一覧", use_container_width=True, type="primary" if st.session_state.app_mode == 'NOTES' else "secondary"):
        st.session_state.app_mode = 'NOTES'
        st.rerun()
    if st.button("📊 テスト結果履歴", use_container_width=True, type="primary" if st.session_state.app_mode == 'HISTORY' else "secondary"):
        st.session_state.app_mode = 'HISTORY'
        st.rerun()
    
    st.markdown("---")
    if github_token:
        st.success("🤖 GitHub AI 連動中\n(外部APIキー不要)")
    else:
        st.error("❌ GitHub トークンが見つかりません。")

# --- 補助関数 ---
def extract_text_from_file(uploaded_file):
    text = ""
    if uploaded_file.name.endswith('.pdf'):
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.getvalue()))
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
    else:
        text = uploaded_file.getvalue().decode("utf-8")
    return text[:10000] # 無料枠の制限を考慮し1万文字程度に調整

def generate_ai_content(prompt):
    """GitHub Modelsを使ってJSON形式でコンテンツを生成する"""
    # 無料で高精度な「gpt-4o-mini」モデルを使用します
    response = ai_client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a helpful assistant that outputs strictly in JSON format."},
            {"role": "user", "content": prompt}
        ],
        model="gpt-4o-mini",
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# =========================================================
# モード 1: 学習フロー (LEARN)
# =========================================================
if st.session_state.app_mode == 'LEARN':
    st.title("🎓 AcademiaStream AI - 学習モード")
    
    if not HAS_LIBS:
        st.error("ライブラリのインストールを待つか、ターミナルで実行してください。")
        st.stop()
    if not github_token:
        st.warning("GitHubの環境変数(GITHUB_TOKEN)が読み込めませんでした。Codespacesを再起動するか設定を確認してください。")
        st.stop()

    # --- Phase 1: UPLOAD ---
    if st.session_state.phase == 'UPLOAD':
        st.header("1. 資料のアップロード")
        uploaded_file = st.file_uploader("資料をドロップまたは選択", type=['pdf', 'txt'])
        topic_name = st.text_input("今回のテーマ名を入力", value="新しい学習テーマ")
        
        if uploaded_file and st.button("資料を読み込んで開始する", type="primary"):
            st.session_state.current_topic = topic_name
            
            with st.status("GitHub AIが資料を解析中...", expanded=True) as status:
                st.write("📄 資料からテキストを抽出しています...")
                document_text = extract_text_from_file(uploaded_file)
                
                st.write("🧠 学習ノート（インプット）を生成しています...")
                notes_prompt = f"""
                大学の資料を読み込み、学生用の学習ノートを作成してください。
                資料の性質を判定し、「プロセス・アルゴリズム型」「用語・概念型」「論理・構造型」のいずれかを `document_type` に入れてください。
                必ず以下のJSON形式のみで出力してください。言語は日本語です。
                {{
                  "document_type": "タイプ名",
                  "overall_summary": "資料全体の目的と結論（300字程度）",
                  "core_question": "この資料を学ぶ上で核心となる問い（1文）",
                  "structured_explanation": [
                    {{"title": "見出し", "content": "概要", "detail": "詳細なメカニズムや理由", "keywords": "関連する重要用語"}}
                  ],
                  "glossary": [
                    {{"term": "用語", "definition": "詳細な定義"}}
                  ]
                }}
                [入力資料]:
                {document_text}
                """
                st.session_state.generated_notes = generate_ai_content(notes_prompt)
                
                st.write("📝 テスト問題（アウトプット）を生成しています...")
                test_prompt = f"""
                以下の[入力資料]に基づき、大学レベルの小テストを作成してください。
                問題数は合計5問（選択式2問、穴埋め式2問、記述式1問）としてください。
                必ず以下のJSON形式のみで出力してください。言語は日本語です。
                {{
                  "test_strategy": "出題の意図（100字）",
                  "questions": [
                    {{
                      "id": "q_choice_1", "type": "choice",
                      "question": "問題文", "options": ["選択肢A", "選択肢B", "選択肢C", "選択肢D"],
                      "correct_answer": "正解の選択肢の文字列を完全一致で", "explanation": "詳しい解説"
                    }},
                    {{
                      "id": "q_fill_1", "type": "fill",
                      "question": "〇〇は【　　】である。", "correct_keywords": ["正解キーワード1"],
                      "explanation": "詳しい解説"
                    }},
                    {{
                      "id": "q_desc_1", "type": "descriptive",
                      "question": "〇〇について説明せよ。", "model_answer": "模範解答",
                      "key_elements": ["必須キーワード1"], "explanation": "詳しい解説"
                    }}
                  ]
                }}
                [入力資料]:
                {document_text}
                """
                st.session_state.generated_test = generate_ai_content(test_prompt)
                
                status.update(label="解析完了！学習を開始します。", state="complete", expanded=False)
                time.sleep(1)
                st.session_state.phase = 'INPUT'
                st.rerun()

    # --- Phase 2: INPUT ---
    elif st.session_state.phase == 'INPUT':
        st.header(f"2. インプット: {st.session_state.current_topic}")
        notes = st.session_state.generated_notes
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.success(f"🤖 AI判定: この資料は **「{notes['document_type']}」** です。")
            st.subheader("📌 全体サマリー")
            st.write(notes['overall_summary'])
            st.info(f"💡 **核心となる問い**: {notes['core_question']}")
            
            st.subheader("📖 構造化解説")
            for section in notes['structured_explanation']:
                with st.expander(section['title'], expanded=True):
                    st.markdown(f"**概要**: {section['content']}")
                    st.markdown(f"**詳細**: {section['detail']}")
                    if section.get('keywords'):
                        st.markdown(f"**重要用語**: {section['keywords']}")

            st.subheader("📚 重要用語集")
            glossary_text = ""
            for item in notes['glossary']:
                glossary_text += f"- **{item['term']}**: {item['definition']}\n"
            st.markdown(glossary_text)
            
            if st.button("テストに進む (Output)", type="primary"):
                st.session_state.notes_history.append({
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "topic": st.session_state.current_topic,
                    "summary": notes['overall_summary'],
                    "content": {s['title']: s['content'] + "\n\n" + s['detail'] for s in notes['structured_explanation']},
                    "glossary": glossary_text
                })
                st.session_state.phase = 'TEST'
                st.rerun()
        with col2:
            st.subheader("🎯 学習のヒント")
            st.markdown("テストでは、用語の暗記だけでなく「なぜそうなるのか」という理由を問う問題も出ます。上の解説をよく読んでおきましょう。")

    # --- Phase 3: TEST ---
    elif st.session_state.phase == 'TEST':
        st.header(f"3. テスト: {st.session_state.current_topic}")
        test_data = st.session_state.generated_test
        st.caption(f"AIの出題意図: {test_data['test_strategy']}")
        
        with st.form("test_form"):
            user_inputs = {}
            counts = {'choice': 1, 'fill': 1, 'descriptive': 1}
            
            for q in test_data['questions']:
                t = q['type']
                if t == 'choice':
                    st.subheader(f"【選択式】 Q{counts['choice']}")
                    user_inputs[q['id']] = st.radio(q['question'], q['options'], index=None)
                    counts['choice'] += 1
                elif t == 'fill':
                    st.subheader(f"【穴埋め式】 Q{counts['fill']}")
                    user_inputs[q['id']] = st.text_input(q['question'])
                    counts['fill'] += 1
                elif t == 'descriptive':
                    st.subheader(f"【記述式】 Q{counts['descriptive']}")
                    user_inputs[q['id']] = st.text_area(q['question'])
                    counts['descriptive'] += 1
                st.markdown("---")
            
            if st.form_submit_button("解答を提出して採点する", type="primary"):
                st.session_state.user_answers = user_inputs
