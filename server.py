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
    
    audio_buffer = b""
    
    try:
        while True:
            try:
                # 0.5 second tak wait karega, agar data nahi aaya toh timeout exception dega
                data = await asyncio.wait_for(websocket.receive_bytes(), timeout=0.5)
                
                if len(data) > 0:
                    audio_buffer += data
                    # Jab tak data aa raha hai, loop chalta rahega
                    
            except asyncio.TimeoutError:
                # 👉 BUTTON CHHODNE PAR TIMEOUT HOGA AUR YAHAN PROCESSING SHURU HOGI!
                if len(audio_buffer) > 0:
                    print("Processing Audio on Cloud...")
                    
                    # Abhi hum STT real mic se test karne ke liye temporary default text rakh rahe hain
                    user_text = "Hello, aap kaun ho?" 
                    
                    # ESP32 ko batayenge ki transcribing khatam
                    await websocket.send_json({"type": "stt", "text": user_text})
                    
                    # AI se jawab lenge
                    ai_response = await ask_free_ai(user_text)
                    print(f"AI Response: {ai_response}")
                    
                    # ESP32 ko 'start' bhejenge taaki Screen par 'Speaking...' aaye aur Amp ON ho
                    # Sahi format: state key ko JSON ke andar standard tarike se bhejna
                    await websocket.send_json({"state": "start", "text": ai_response})
                    
                    # Audio generate karenge
                    audio_response = await text_to_speech(ai_response)
                    
                    # ESP32 ko audio data chunks bhejenge
                    chunk_size = 1024
                    for i in range(0, len(audio_response), chunk_size):
                        await websocket.send_bytes(audio_response[i:i+chunk_size])
                        await asyncio.sleep(0.01)
                    
                    # Bolna khatam hone par 'stop' state bhejenge (Amp OFF + Emoji Reset)
                    await websocket.send_json({"state": "stop"})
                    
                    # Buffer ko khali kar denge agle command ke liye
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
