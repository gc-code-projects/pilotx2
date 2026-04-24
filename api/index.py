from flask import Flask, render_template, request, jsonify
import os
import asyncio
from volcenginesdkarkruntime import Ark, AsyncArk

# 👇 IMPORTANT: point to templates folder correctly
app = Flask(__name__, template_folder="../templates")

# =========================
# Global initialization
# =========================
api_key = os.getenv("LLM_API_KEY")
MODEL = "doubao-seed-2-0-mini-260215"

client = None
if api_key:
    client = Ark(
        base_url='https://ark.cn-beijing.volces.com/api/v3',
        api_key=api_key,
    )

# =========================
# Routes
# =========================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/historical-materials')
def historical_materials():
    return render_template('historical-materials.html')

@app.route('/historical-analysis')
def historical_analysis():
    return render_template('historical-analysis.html')

@app.route('/time-travel')
def time_travel():
    return render_template('time-travel.html')

@app.route('/time-travel-scenario')
def time_travel_scenario():
    return render_template('time-travel-scenario.html')

@app.route('/quiz')
def quiz():
    return render_template('quiz.html')
    
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        prompt = data.get('message', '')

        if not client:
            return jsonify({'response': 'AI服务不可用，请检查API Key'})

        response = client.responses.create(
            model=MODEL,
            input=prompt,
        )

        return jsonify({
            'response': response.output[1].content[0].text
        })

    except Exception as e:
        return jsonify({'response': f'错误: {str(e)}'})


# =========================
# Upload (single PDF)
# =========================
@app.route('/upload', methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({"message": "No file part"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"message": "No selected file"}), 400

        if not file.filename.lower().endswith('.pdf'):
            return jsonify({"message": "请上传 PDF 文件"}), 400

        # ⚠️ Vercel: use /tmp (writable)
        uploads_dir = "/tmp"
        file_path = os.path.join(uploads_dir, file.filename)
        file.save(file_path)

        analysis = analyze_pdf(file_path, "请分析这个PDF文件")

        return jsonify({
            "message": f"{file.filename} 上传并分析成功",
            "ai_analysis": analysis
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# Upload (multiple PDFs)
# =========================
@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        if 'file' not in request.files:
            return jsonify({"message": "No file part"}), 400

        files = request.files.getlist('file')
        task = request.form.get('task', '请分析这些PDF文件')

        results = []

        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                return jsonify({"message": "请上传 PDF 文件"}), 400

            file_path = os.path.join("/tmp", file.filename)
            file.save(file_path)

            analysis = analyze_pdf(file_path, task)

            results.append({
                "filename": file.filename,
                "analysis": analysis
            })

        combined = "# PDF分析结果\n\n"
        for r in results:
            combined += f"## {r['filename']}\n{r['analysis']}\n\n"

        return jsonify({
            "message": f"{len(files)} 个文件分析完成",
            "ai_analysis": combined
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# PDF Analysis (ASYNC)
# =========================
def analyze_pdf(file_path, task):
    async def run():
        try:
            async_client = AsyncArk(
                base_url='https://ark.cn-beijing.volces.com/api/v3',
                api_key=api_key
            )

            # Upload
            with open(file_path, "rb") as f:
                file = await async_client.files.create(
                    file=f,
                    purpose="user_data"
                )

            await async_client.files.wait_for_processing(file.id)

            response = await async_client.responses.create(
                model=MODEL,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": file.id},
                        {"type": "input_text", "text": task}
                    ]
                }]
            )

            if response and len(response.output) > 1:
                return response.output[1].content[0].text

            return "未获取到分析结果"

        except Exception as e:
            return f"分析错误: {str(e)}"

    return asyncio.run(run())


# =========================
# 👇 Vercel entrypoint
# =========================
def handler(request, *args, **kwargs):
    return app(request.environ, lambda *args: None)