import os
import requests
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent
from google import genai
from google.genai import types

app = Flask(__name__)

# ดึงค่าจาก Environment Variables บน Render
configuration = Configuration(access_token=os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))

# ตั้งค่า Gemini API Client (ให้ใส่ GEMINI_API_KEY ใน Environment Variables ของ Render ด้วย)
gemini_client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, InvalidSignatureError)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ข้อ 6.1 และ 6.2: จัดการข้อความตัวอักษร
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_message = event.message.text.strip()
    
    # โจทย์ข้อ 6.1: เช็ค Keyword "คุณเป็นใคร"
    if user_message == "คุณเป็นใคร":
        reply_text = (
            "รหัสทีม: [ใส่รหัสทีมของคุณ]\n"
            "สมาชิก:\n1. [ชื่อ-นามสกุล คนที่ 1]\n2. [ชื่อ-นามสกุล คนที่ 2]\n"
            "โรงเรียน: [ใส่ชื่อโรงเรียนของคุณ]"
        )
    else:
        # โจทย์ข้อ 6.2: ส่งคำถามทั่วไปให้ Gemini AI ตอบ
        try:
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_message,
            )
            reply_text = response.text
        except Exception as e:
            reply_text = f"ขออภัย เกิดข้อผิดพลาดในการประมวลผล: {str(e)}"

    # ส่งข้อความกลับหาผู้ใช้ทาง Line
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

# โจทย์ข้อ 6.3: จัดการรูปภาพเพื่อวิเคราะห์สายพันธุ์สัตว์
@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    message_id = event.message.id
    access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
    
    # 1. ดึงไฟล์รูปภาพจาก LINE Messaging API
    headers = {'Authorization': f'Bearer {access_token}'}
    image_url = f'https://api-data.line.me/v2/bot/message/{message_id}/content'
    img_response = requests.get(image_url, headers=headers)
    
    if img_response.status_code == 200:
        image_bytes = img_response.content
        
        # 2. ส่งต่อให้ Gemini API วิเคราะห์รูปภาพ
        try:
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type='image/jpeg',
                    ),
                    'ภาพนี้คือสัตว์ประเภทอะไร ช่วยอธิบายสั้นๆ'
                ]
            )
            reply_text = response.text
        except Exception as e:
            reply_text = f"ไม่สามารถวิเคราะห์รูปภาพได้: {str(e)}"
    else:
        reply_text = "ไม่สามารถดาวน์โหลดรูปภาพจาก LINE ได้"

    # 3. ส่งคำตอบกลับหาผู้ใช้
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    app.run(port=5000)