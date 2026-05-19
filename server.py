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

# 👇 YAHAN APNI GOOGLE GEMINI KI API KEY PASTE KAREIN 👇
GEMINI_API_KEY = "AIzaSyAsz2YpauZNIvqGHQInH2Ij_cPzOf-YF_E"

try:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
    print("Gemini AI Initialized Successfully!")
except Exception as e:
    print(f"Gemini API Error: {e}")
    ai_client = None

async def ask_gemini_ai(prompt):
    try:
        if ai_client:
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return response.text
        else:
            return "Main aapka Jarvis assistant hoon. API key check kijiye!"
    except Exception as e:
        print(f"AI Error: {e}")
        return "Maaf kijiyega, main abhi theek se soch nahi pa raha hoon."

async def text_to_speech(text):
    # 'MadhurNeural' ek bohot badiya Hindi male voice hai
    communicate = edge_tts.Communicate(text, "hi-IN-MadhurNeural")
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

# 🎙️ REAL SPEECH TO TEXT FUNCTION
def convert_audio_to_text(raw_data):
    try:
        # ESP32 se 16kHz, 32-bit raw audio aata hai, use WAV mein badlenge
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
            # Google Free Speech Recognition (Hindi aur English dono samajhta hai)
            text = recognizer.recognize_google(audio_file_data, language="hi-IN")
            return text
    except sr.UnknownValueError:
        print("STT: Awaaz samajh nahi aayi.")
        return None
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
                # 0.5 sec ka timeout (Button chhodne ka intezaar)
                data = await asyncio.wait_for(websocket.receive_bytes(), timeout=0.5)
                if len(data) > 0:
                    audio_buffer += data
            except asyncio.TimeoutError:
                if len(audio_buffer) > 0:
                    print("Processing Audio on Cloud...")
                    
                    # 🚀 ASLI VOICE RECOGNITION (Mic ki awaaz text banegi)
                    user_text = convert_audio_to_text(audio_buffer)
                    
                    if not user_text:
                        user_text = "Hello" # Agar mic khali chhoot jaye toh default word
                    
                    print(f"User Said: {user_text}")
                    # ESP32 ki screen par "Listening" ko text se update karne ke liye
                    await websocket.send_json({"type": "stt", "text": user_text})
                    
                    # Gemini se asli jawab mangna
                    ai_response = await ask_gemini_ai(user_text)
                    print(f"AI Response: {ai_response}")
                    
                    # ESP32 ka Amplifier ON aur Animation start
                    await websocket.send_json({"state": "start", "text": ai_response})
                    
                    # AI ke jawab ko audio mein badal kar ESP32 ko bhejna
                    audio_response = await text_to_speech(ai_response)
                    
                    chunk_size = 1024
                    for i in range(0, len(audio_response), chunk_size):
                        await websocket.send_bytes(audio_response[i:i+chunk_size])
                        await asyncio.sleep(0.01)
                    
                    # ESP32 ka Amplifier OFF aur Idle Animation
                    await websocket.send_json({"state": "stop"})
                    
                    # Agli recording ke liye buffer khali
                    audio_buffer = b""
                    
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
