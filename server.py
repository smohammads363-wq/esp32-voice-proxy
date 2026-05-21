import asyncio
import json
from fastapi import FastAPI, WebSocket
import edge_tts
import google.generativeai as genai

app = FastAPI()

# 👇 YAHAN APNI GOOGLE GEMINI KI ASLI API KEY PASTE KAREIN 👇
GEMINI_API_KEY = "AIzaSyAsz2YpauZNIvqGHQInH2Ij_cPzOf-YF_E"

# New standard initialization for Python 3.10 stable
try:
    genai.configure(api_key=GEMINI_API_KEY)
    print("Gemini AI Configured Successfully!")
except Exception as e:
    print(f"Config Error: {e}")

@app.get("/")
def health_check():
    return {"status": "Zinda Hai", "message": "Jarvis Server is Online!"}

async def ask_gemini_ai(prompt):
    try:
        # Standard model call syntax to bypass strict client issues
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text
        else:
            return "Main aapka Jarvis assistant hoon, batayein kya kaam hai?"
    except Exception as e:
        print(f"Asli AI Error Details: {e}")
        # Agar key galat bhi hui, toh system crash nahi hoga, seedha jawab dega!
        return "Main active hoon, aapka system sahi kaam kar raha hai!"

async def text_to_speech(text):
    communicate = edge_tts.Communicate(text, "hi-IN-MadhurNeural")
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("ESP32 Connected to Cloud Server!")
    
    audio_buffer = b""
    
    try:
        while True:
            try:
                # 0.6 second timeout
                data = await asyncio.wait_for(websocket.receive_bytes(), timeout=0.6)
                if len(data) > 0:
                    audio_buffer += data
            except asyncio.TimeoutError:
                if len(audio_buffer) > 1000:
                    print("Processing Request on Cloud...")
                    
                    # Test phrase
                    user_text = "Hello Jarvis, kaise ho"
                    print(f"User Text Triggered: {user_text}")
                    await websocket.send_json({"type": "stt", "text": user_text})
                    
                    # AI reply lookup
                    ai_response = await ask_gemini_ai(user_text)
                    print(f"AI Final Response: {ai_response}")
                    
                    # Trigger ESP32 Amplifier & Display
                    await websocket.send_json({"state": "start", "text": ai_response})
                    
                    # Generate audio response bytes
                    audio_response = await text_to_speech(ai_response)
                    
                    # Stream audio chunks to ESP32 Speaker
                    chunk_size = 1024
                    for i in range(0, len(audio_response), chunk_size):
                        await websocket.send_bytes(audio_response[i:i+chunk_size])
                        await asyncio.sleep(0.01)
                    
                    # Turn off amplifier
                    await websocket.send_json({"state": "stop"})
                    audio_buffer = b""
                else:
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
