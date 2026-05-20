import asyncio
import json
import io
from fastapi import FastAPI, WebSocket
import edge_tts
from google import genai
import speech_recognition as sr
from pydub import AudioSegment

app = FastAPI()
recognizer = sr.Recognizer()

# 🎛️ NOISE FILTER: Yeh dheemi aawaz aur kachre ko kaat dega
recognizer.energy_threshold = 300  # Aapke 150 noise floor se upar set kiya hai
recognizer.dynamic_energy_threshold = False

# 👇 APNI GEMINI KEY IN DO QUOTES COPIED KAREIN 👇
GEMINI_API_KEY = "AIzaSyAsz2YpauZNIvqGHQInH2Ij_cPzOf-YF_E"

try:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
    print("Gemini AI Initialized Successfully!")
except Exception as e:
    print(f"Gemini API Error: {e}")
    ai_client = None

@app.get("/")
def health_check():
    return {"status": "Zinda Hai", "message": "Jarvis Server is Running!"}

async def ask_gemini_ai(prompt):
    try:
        if ai_client:
            # Sahi Free Model: gemini-1.5-flash
            response = ai_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt
            )
            return response.text
        else:
            return "Main aapka Jarvis assistant hoon. API key check kijiye!"
    except Exception as e:
        print(f"AI Error: {e}")
        return "Maaf kijiyega, mujhe jawab nahi mila."

async def text_to_speech(text):
    communicate = edge_tts.Communicate(text, "hi-IN-MadhurNeural")
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

def convert_audio_to_text(raw_data):
    try:
        # ESP32 ke raw data ko clean WAV mein convert karna
        audio_segment = AudioSegment.from_raw(
            io.BytesIO(raw_data), 
            sample_width=4, 
            frame_rate=16000, 
            channels=1
        )
        wav_io = io.BytesIO()
        audio_segment.export(wav_io, format="wav")
        wav_io.seek(0)
        
        with sr.AudioFile(wav_io) as source:
            audio_file_data = recognizer.record(source)
            # Hindi + English Auto Detect
            text = recognizer.recognize_google(audio_file_data, language="hi-IN")
            return text
    except Exception as e:
        print(f"STT Error: {e}")
        return None

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("ESP32 Connected to Cloud Server!")
    
    audio_buffer = b""
    
    try:
        while True:
            try:
                # 0.6 second ka stable timeout
                data = await asyncio.wait_for(websocket.receive_bytes(), timeout=0.6)
                if len(data) > 0:
                    audio_buffer += data
            except asyncio.TimeoutError:
                if len(audio_buffer) > 2000: # Bohot chote kachre data ko ignore karega
                    print("Processing Audio on Cloud...")
                    
                    user_text = convert_audio_to_text(audio_buffer)
                    
                    if not user_text or user_text.strip() == "":
                        # Agar kuch samajh na aaye toh blank chhodne ke bajaye ek achha sawal auto-assume karein
                        user_text = "Tum kaun ho" 
                    
                    print(f"User Said: {user_text}")
                    await websocket.send_json({"type": "stt", "text": user_text})
                    
                    ai_response = await ask_gemini_ai(user_text)
                    print(f"AI Response: {ai_response}")
                    
                    await websocket.send_json({"state": "start", "text": ai_response})
                    
                    audio_response = await text_to_speech(ai_response)
                    
                    chunk_size = 1024
                    for i in range(0, len(audio_response), chunk_size):
                        await websocket.send_bytes(audio_response[i:i+chunk_size])
                        await asyncio.sleep(0.01)
                    
                    await websocket.send_json({"state": "stop"})
                    audio_buffer = b""
                else:
                    audio_buffer = b"" # Clear chota floating noise
                    
    except Exception as e:
        print(f"Disconnected: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
