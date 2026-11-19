import json
import os
import re
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


MAX_JPY_AMOUNT = 99_999_999_999
PAYMENT_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


class PayPayAPIError(Exception):
    pass


class PayPayService:
    def __init__(self, client, amount, order_description):
        self.client = client
        self.amount = amount
        self.order_description = order_description

    def create_payment(self):
        merchant_payment_id = str(uuid.uuid4())
        response = self.client.Code.create_qr_code(
            {
                "merchantPaymentId": merchant_payment_id,
                "codeType": "ORDER_QR",
                "orderDescription": self.order_description,
                "amount": {"amount": self.amount, "currency": "JPY"},
            }
        )
        data = self._successful_data(response)
        checkout_url = data.get("url") or data.get("deepLink")
        if not checkout_url:
            raise PayPayAPIError("PayPay response did not include a checkout URL")
        return {
            "merchantPaymentId": merchant_payment_id,
            "checkoutUrl": checkout_url,
        }

    def get_payment(self, merchant_payment_id):
        response = self.client.Code.get_payment_details(merchant_payment_id)
        data = self._successful_data(response)
        status = data.get("status")
        if not status:
            raise PayPayAPIError("PayPay response did not include a payment status")
        return {
            "merchantPaymentId": merchant_payment_id,
            "status": status,
            "paymentId": data.get("paymentId"),
        }

    @staticmethod
    def _successful_data(response):
        if not isinstance(response, dict):
            raise PayPayAPIError("Invalid response from PayPay")
        result_info = response.get("resultInfo")
        data = response.get("data")
        if (
            not isinstance(result_info, dict)
            or result_info.get("code") != "SUCCESS"
            or not isinstance(data, dict)
        ):
            raise PayPayAPIError("PayPay request was not successful")
        return data


def make_handler(service):
    class PayPayRequestHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if urlsplit(self.path).path != "/api/payments":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                return
            if self.headers.get("Transfer-Encoding") or self.headers.get(
                "Content-Length", "0"
            ) != "0":
                self.close_connection = True
                self._send_json(
                    HTTPStatus.BAD_REQUEST, {"error": "Request body must be empty"}
                )
                return
            try:
                payment = service.create_payment()
            except Exception:
                self._send_json(
                    HTTPStatus.BAD_GATEWAY, {"error": "Unable to create PayPay payment"}
                )
                return
            self._send_json(HTTPStatus.CREATED, payment)

        def do_GET(self):
            path = urlsplit(self.path).path
            prefix = "/api/payments/"
            if not path.startswith(prefix):
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                return
            merchant_payment_id = path[len(prefix) :]
            if not PAYMENT_ID_PATTERN.fullmatch(merchant_payment_id):
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                return
            try:
                payment = service.get_payment(merchant_payment_id)
            except Exception:
                self._send_json(
                    HTTPStatus.BAD_GATEWAY, {"error": "Unable to retrieve PayPay payment"}
                )
                return
            self._send_json(HTTPStatus.OK, payment)

        def _send_json(self, status, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            pass

    return PayPayRequestHandler


def create_service():
    api_key = os.environ.get("PAYPAY_API_KEY")
    api_secret = os.environ.get("PAYPAY_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("PAYPAY_API_KEY and PAYPAY_API_SECRET must be set")

    try:
        amount = int(os.environ.get("PAYPAY_ORDER_AMOUNT", "100"))
    except ValueError as exc:
        raise RuntimeError("PAYPAY_ORDER_AMOUNT must be a positive integer") from exc
    if not 0 < amount <= MAX_JPY_AMOUNT:
        raise RuntimeError("PAYPAY_ORDER_AMOUNT is outside the supported range")

    order_description = os.environ.get(
        "PAYPAY_ORDER_DESCRIPTION", "Sample order"
    ).strip()
    if not order_description or len(order_description) > 255:
        raise RuntimeError(
            "PAYPAY_ORDER_DESCRIPTION must contain 1 to 255 characters"
        )

    environment = os.environ.get("PAYPAY_ENVIRONMENT", "sandbox").lower()
    if environment not in {"sandbox", "production"}:
        raise RuntimeError("PAYPAY_ENVIRONMENT must be sandbox or production")

    import paypayopa

    client = paypayopa.Client(
        auth=(api_key, api_secret),
        production_mode=(environment == "production"),
    )
    return PayPayService(client, amount, order_description)


def main():
    service = create_service()
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(service))
    print(f"PayPay API listening on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
