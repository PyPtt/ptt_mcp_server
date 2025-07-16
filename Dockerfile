# --- 第一階段：建置環境 (Builder Stage) ---
# 使用標準的 Python 映像來安裝套件，這個映像包含完整的建置工具
FROM python:3.10-alpine AS builder

# 設定工作目錄
WORKDIR /app

# 建立一個虛擬環境，這有助於隔離並只複製必要的套件
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 只複製 requirements.txt，這樣可以利用 Docker 的快取機制
# 只有當 requirements.txt 變動時，才會重新安裝套件
COPY requirements.txt .

# 安裝 Python 套件，--no-cache-dir 可以減少 image 大小
RUN pip install --no-cache-dir -r requirements.txt

# 複製您的應用程式原始碼
COPY src/ ./src/


# --- 第二階段：執行環境 (Final Stage) ---
# 使用更輕量的 slim 版本作為最終的執行環境
FROM python:3.10-alpine

# 設定工作目錄
WORKDIR /app

# 從建置環境中，只複製包含已安裝套件的虛擬環境
COPY --from=builder /opt/venv /opt/venv

# 從建置環境中，只複製應用程式的原始碼
COPY --from=builder /app/src ./src

# 設定環境變數，讓應用程式使用虛擬環境中的 Python
ENV PATH="/opt/venv/bin:$PATH"

# 設定應用程式的啟動指令
# 假設您的主程式是 mcp_server.py
CMD ["python", "src/mcp_server.py"]