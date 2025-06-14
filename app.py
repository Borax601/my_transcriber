import os
import time
from flask import Flask, request
from werkzeug.utils import secure_filename
import google.generativeai as genai

# --- 設定 (Configuration) ---
UPLOAD_FOLDER = os.path.join(os.path.expanduser('~'), 'Desktop', 'uploads')
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

try:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("エラー: 環境変数 GOOGLE_API_KEY が設定されていません。")
    genai.configure(api_key=api_key)
    print("Gemini APIキーの認証に成功しました。")
except Exception as e:
    print(e)

# --- HTMLテンプレート (入力欄が追加されたバージョン) ---
HTML_FORM = """
<!doctype html>
<html lang='ja'>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>音声ファイルをアップロード</title>
  <style>
    body {
      font-family: 'Segoe UI', 'Hiragino Sans', 'Meiryo', sans-serif;
      background: #f5f7fa;
      margin: 0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }
    .container {
      background: #fff;
      border-radius: 24px;
      box-shadow: 0 2px 16px rgba(0,0,0,0.08);
      padding: 2em 1em;
      margin: 3em auto;
      width: 90vw;
      max-width: 800px;
      min-width: 280px;
      min-height: 300px;
      display: flex;
      flex-direction: column;
      align-items: center;
      box-sizing: border-box;
    }
    @media (max-width: 600px) {
      .container {
        width: 98vw;
        max-width: 100vw;
        margin: 0.5em auto;
        padding: 1em 0.2em;
      }
    }
    .form-group {
      width: 100%;
      margin-bottom: 1.2em;
    }
    label {
      display: block;
      margin-bottom: 0.3em;
      font-weight: 500;
    }
    input[type='text'] {
      width: 100%;
      padding: 0.6em;
      border: 1px solid #bfc6d1;
      border-radius: 7px;
      font-size: 1em;
      box-sizing: border-box;
      margin-bottom: 0.2em;
    }
    input[type='file'] {
      width: 100%;
      margin-top: 0.3em;
    }
    input[type='submit'] {
      background: #1976d2;
      color: #fff;
      border: none;
      border-radius: 7px;
      padding: 0.8em 2em;
      font-size: 1.1em;
      font-weight: bold;
      cursor: pointer;
      margin-top: 0.7em;
      box-shadow: 0 2px 8px rgba(25, 118, 210, 0.10);
      transition: background 0.2s;
    }
    input[type='submit']:hover {
      background: #1565c0;
    }
    .title {
      color: #1976d2;
      font-size: 1.6em;
      font-weight: bold;
      text-align: center;
      margin: 0.5em 0 1.2em 0;
      letter-spacing: 0.04em;
    }
    .top-img {
      width: 90px;
      margin-bottom: 0.5em;
    }
    @media (max-width: 600px) {
      .container {
        padding: 1.2em 0.3em 1.5em 0.3em;
        max-width: 98vw;
      }
      .top-img {
        width: 65px;
      }
      .title {
        font-size: 1.1em;
    }
  </style>
</head>
<body>
  <div class="container">
    <div style="width:100%; display: flex; justify-content: center; margin-bottom: 0.5em; margin-top: 0.5em;">
      <img src="/static/flask_run_port_5001.png" alt="説明画像" style="max-width: 200px; width: 30vw; height: auto; display: block; margin: 0 auto;" loading="lazy">
    </div>
    <div class="title" style="text-align:center; margin-bottom: 1em;">
      <span style="font-size:2rem; font-weight:bold; display:inline-block;">音声ファイルをアップロードして文字起こし＆要約</span>
    </div>
    <form method="post" action="/upload" enctype="multipart/form-data" style="width:100%;">
      <div class="form-group">
        <label for="conversation_type">会話の種類</label>
        <input type="text" id="conversation_type" name="conversation_type" placeholder="例：診察">
      </div>
      <div class="form-group">
        <label for="participants">参加者（例：医師と患者、上司Aと部下B）</label>
        <input type="text" id="participants" name="participants" placeholder="例：医師と患者">
      </div>
      <div class="form-group">
        <span style="font-size:0.98em; color:#555;">対応ファイル形式：mp3, wav, aiff, m4a など</span><br>
        <input type="file" name="audio_file" accept="audio/*">
      </div>
      <input type="submit" value="実行">
    </form>
  </div>
</body>
</html>
"""

RESULT_HTML = """
<!doctype html>
<title>処理結果</title>
<style>
  body {{ font-family: sans-serif; margin: 2em; }}
  .result-box {{ margin-top: 1em; padding: 1em; border: 1px solid #ccc; background-color: #f9f9f9; white-space: pre-wrap; border-radius: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }}
</style>
<h1 style="color: #2386e6; font-size:2.1rem; font-weight:bold;">処理結果</h1>
<h2 style="color: #2386e6; font-size:1.4rem; font-weight:bold;">文字起こし全文</h2>
<div class="result-box">{transcribed_text}</div>
<h2 style="color: #2386e6; font-size:1.4rem; font-weight:bold;">要約</h2>
<div class="result-box">{summary_text}</div>
<br>
<a href="/">別のファイルを試す</a>
"""

# --- Flaskのルート定義 ---
@app.route('/')
def show_upload_form():
    return HTML_FORM

@app.route('/upload', methods=['POST'])
def handle_upload_and_process():
    if 'audio_file' not in request.files:
        return "エラー: リクエストにファイルパートがありません"
    file = request.files['audio_file']
    if file.filename == '':
        return "エラー: ファイルが選択されていません"
    if file:
        filename = secure_filename(file.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        print(f"ファイル '{filename}' を '{save_path}' に保存しました。")
        try:
            # 入力フォームから会話の種類・参加者を取得
            conversation_type = request.form.get("conversation_type", "")
            participants = request.form.get("participants", "")

            import mimetypes
            print("Geminiにファイルをアップロードしています...")
            mime_type, _ = mimetypes.guess_type(save_path)
            if not mime_type:
                mime_type = "audio/m4a"  # デフォルト（必要に応じて他形式も対応可）
            gemini_file = genai.upload_file(path=save_path, mime_type=mime_type)
            print(f"mime_type: {mime_type}")
            print("Gemini側でのファイル処理を待っています...")
            while gemini_file.state.name == "PROCESSING":
                time.sleep(2)
                gemini_file = genai.get_file(name=gemini_file.name)
            if gemini_file.state.name == "FAILED":
                return f"エラー: Geminiへのファイルアップロードに失敗しました。"
            print("ファイル準備完了。文字起こしを開始します...")
            model = genai.GenerativeModel(model_name='models/gemini-1.5-flash-latest')

            # --- ここでプロンプトに会話の種類・参加者・話者分離を明示的に指示 ---
            # 参加者リストを抽出し、話者名候補としてプロンプトで強調
            participants_list = [p.strip() for p in participants.replace('、', ',').replace('と', ',').split(',') if p.strip()]
            participants_bullet = '\n'.join(f'- {p}' for p in participants_list)
            prompt_transcribe = f"""
この音声ファイルは『{conversation_type}』の会話で、参加者は以下の通りです：
{participants_bullet}

【厳守事項】
- 発言ごとに必ず話者名（上記の候補から選択、例：{', '.join(participants_list)}）を付与してください。
- 話者が変わるたびに必ず改行し、話者名：発言内容 の形式で日本語で正確に文字起こししてください。
- 1人の発言に複数文が含まれる場合も、話者名を省略せず毎回付与してください。
- 話者が特定できない場合は「不明」などと記載してください。

【出力例】
講師A：こんにちは。今日はよろしくお願いします。
私B：よろしくお願いします。
講師A：まず最初に・・・

上記の形式を厳密に守ってください。
"""
            response_transcribe = model.generate_content(
                [prompt_transcribe, gemini_file],
                request_options={"timeout": 600}
            )
            transcribed_text = response_transcribe.text
            print("文字起こし完了。")

            # --- 話者分離の再プロンプト処理 ---
            import re
            # 参加者名が十分に含まれているか判定（例：最低2人の話者名が登場しているか）
            speaker_count = 0
            for p in participants_list:
                if re.search(re.escape(p) + r'：', transcribed_text):
                    speaker_count += 1
            if speaker_count < max(2, len(participants_list)):
                print("話者分離が不十分なため、再プロンプトします...")
                reprompt = f"""
以下は話者分離が不十分な文字起こし結果です。必ず発言ごとに話者名（{', '.join(participants_list)} など）を付与し、話者が変わるたびに改行してください。

---
{transcribed_text}
---

【厳守事項】
- 発言ごとに必ず話者名を付与してください。
- 話者名が特定できない場合は「不明」としてください。
- 例：\n講師A：こんにちは。\n私B：よろしくお願いします。
"""
                response_transcribe2 = model.generate_content(
                    reprompt,
                    request_options={"timeout": 600}
                )
                transcribed_text = response_transcribe2.text
                print("再話者分離完了。")

            print("要約を開始します...")
            prompt_summarize = f"この会話は『{conversation_type}』で、参加者は『{participants}』です。\n\n以下の議事録を、重要なポイントを箇条書きでまとめてください。\n\n---\n\n{transcribed_text}"
            response_summarize = model.generate_content(
                prompt_summarize,
                request_options={"timeout": 120}
            )
            summary_text = response_summarize.text
            print("要約完了。")
            genai.delete_file(name=gemini_file.name)

            # --- 話者交代ごとに改行を挿入する整形処理 ---
            import re
            speakers = participants_list + ["医者", "患者", "不明"]
            pattern = r"(?<!^)" + r"|".join([fr"(?<!\n)({re.escape(s)}：)" for s in speakers])
            # 既に行頭にある場合は除外し、そうでなければ直前に改行を挿入
            transcribed_text_fmt = re.sub(pattern, lambda m: "\n" + m.group(0), transcribed_text)

            return RESULT_HTML.format(
                transcribed_text=transcribed_text_fmt,
                summary_text=summary_text
            )
        except Exception as e:
            print(f"エラーが発生しました: {e}")
            return f"処理中にエラーが発生しました: {e}"
    return "予期せぬエラーが発生しました。"
