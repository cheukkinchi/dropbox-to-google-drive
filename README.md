# Dropbox to Google Drive Migration

這個專案提供一個 Python 指令稿，透過 Dropbox 與 Google Drive 的官方 API，將指定資料夾或整個 Dropbox 空間的檔案遷移至 Google Drive。

## 功能特色

- 以遞迴方式列出 Dropbox 指定路徑下所有檔案與資料夾。
- 將 Dropbox 的目錄結構在 Google Drive 中重建。
- 透過 MIME type 自動判斷檔案格式並上傳至 Google Drive。
- 若目標資料夾中已存在同名檔案可自動略過，避免重複上傳。
- 可選擇遷移 Dropbox 上的特定子資料夾，並指定 Google Drive 的目標子資料夾。

## 需求安裝

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 取得 API 憑證

1. **Dropbox**：在 [Dropbox App Console](https://www.dropbox.com/developers/apps) 建立應用程式並產生存取權杖 (Access Token)。建議使用長期 Token。
2. **Google Drive**：在 [Google Cloud Console](https://console.cloud.google.com/) 建立專案，啟用 Drive API 並建立 Service Account。下載 JSON 金鑰，並確保已將欲遷移到的 Google Drive 目錄與該 Service Account 分享。

## 使用方式

```bash
python -m src.dropbox_to_gdrive <DROPBOX_TOKEN> <GOOGLE_SERVICE_ACCOUNT_JSON> \
    [--dropbox-path "/要遷移的/dropbox/資料夾"] \
    [--drive-path "Google Drive/目標/資料夾"] \
    [--log-level INFO]
```

### 範例

將整個 Dropbox 搬移到 Google Drive 的 `Dropbox 備份` 資料夾下：

```bash
python -m src.dropbox_to_gdrive $DROPBOX_TOKEN service-account.json \
    --drive-path "Dropbox 備份"
```

僅遷移 Dropbox 中的 `/Projects/2024` 資料夾到 Google Drive `備份/Projects` 底下：

```bash
python -m src.dropbox_to_gdrive $DROPBOX_TOKEN service-account.json \
    --dropbox-path "/Projects/2024" \
    --drive-path "備份/Projects"
```

## 注意事項

- 大量資料建議使用 Service Account，並在 Google Drive 中提前建立對應目錄與分享權限。
- Dropbox 與 Google Drive 的 API 皆有限流，若遇到 `HttpError` 或 Rate Limit，可稍後再試或於程式中加入重試機制。
- 目前指令稿會略過在 Google Drive 中已存在的同名檔案，若需要覆蓋請自行修改 `upload_file` 中的邏輯。

## License

MIT
