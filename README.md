# Yu-lin-ke

## PayPay 收款 API（Python）

此範例使用 PayPay 官方 `paypayopa` Python SDK，在伺服器端建立動態 QR 付款，並提供付款狀態查詢 API。SDK 維護有限，請同時核對 [PayPay 最新 API 文件](https://developer.paypay.ne.jp/products/docs/webpayment)。

### 設定與啟動

需要 Python 3.8 以上，以及 PayPay 商家帳戶和開發者後台提供的 API 金鑰。先在 PayPay Sandbox 建立並測試憑證：

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export PAYPAY_API_KEY='sandbox-api-key'
export PAYPAY_API_SECRET='sandbox-api-secret'
export PAYPAY_ENVIRONMENT=sandbox
export PAYPAY_ORDER_AMOUNT=100
export PAYPAY_ORDER_DESCRIPTION='Sample order'
python paypay_api.py
```

`PAYPAY_ENVIRONMENT` 預設為 `sandbox`。只有在商家正式環境已核准並設定正式憑證後，才可明確設為 `production`。金額由伺服器端環境變數設定，API 不接受客戶端指定金額。

### API

建立付款（固定使用伺服器設定的 JPY 金額）：

```sh
curl -X POST http://127.0.0.1:8000/api/payments
```

成功時會回傳 `merchantPaymentId` 和 PayPay `checkoutUrl`。顧客完成付款後，以回傳的 ID 查詢狀態：

```sh
curl http://127.0.0.1:8000/api/payments/<merchantPaymentId>
```

只有 PayPay 查詢結果的付款狀態為 `COMPLETED` 時，商家系統才應將訂單視為已付款；不能只依顧客返回頁面或前端結果確認付款。

### 上線前注意事項

- 範例僅綁定 `127.0.0.1`，使用記憶體外的訂單／付款資料庫、使用者驗證、授權、HTTPS、速率限制及正式部署設定仍需由商家自行加入。
- 請勿將 API 金鑰寫入程式碼、前端、版本控制或日誌。
- 正式商店應從伺服器端的真實訂單資料計算金額，並持久化商家付款 ID，避免重複建立或錯誤對帳。
- 本範例建立的是動態 QR 付款；請依 PayPay 商家合約、地區資格及最新文件確認可用付款流程。

### 測試

```sh
python -m unittest
```
