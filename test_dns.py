import socket

try:
    ip = socket.gethostbyname("api.groq.com")
    print("✅ DNS resolvido:", ip)
except Exception as e:
    print("❌ Erro ao resolver DNS:", e)
