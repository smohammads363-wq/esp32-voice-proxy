import asyncio
import json
from fastapi import FastAPI, WebSocket
import edge_tts
from g4f.client import AsyncClient

app = FastAPI()
ai_client = AsyncClient()

async def ask_free_ai(prompt):
    try:
        response = await ai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI Error: {e}")
        return "Maaf kijiyega, mujhe jawab dhundhne mein thodi dikkat ho rahi hai."

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
    
    try:
        while True:
            data = await websocket.receive_bytes()
            
            if len(data) == 0 or b"END_OF_SPEECH" in data:
                print("Processing Audio on Cloud...")
                user_text = "Hello, aap kaun ho?" 
                
                await websocket.send_json({"type": "stt", "text": user_text})
                
                ai_response = await ask_free_ai(user_text)
                await websocket.send_json({"type": "tts", "state": "start", "text": ai_response})
                
                audio_response = await text_to_speech(ai_response)
                
                chunk_size = 1024
                for i in range(0, len(audio_response), chunk_size):
                    await websocket.send_bytes(audio_response[i:i+chunk_size])
                    await asyncio.sleep(0.01)
                    
                await websocket.send_json({"type": "tts", "state": "stop"})
            else:
                pass
                
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
