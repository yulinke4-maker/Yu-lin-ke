import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from paypay_api import PayPayAPIError, PayPayService, make_handler


class PayPayServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.service = PayPayService(self.client, 250, "Test order")

    def test_create_payment_uses_configured_jpy_amount(self):
        self.client.Code.create_qr_code.return_value = {
            "resultInfo": {"code": "SUCCESS"},
            "data": {"url": "https://paypay.example/checkout"},
        }

        result = self.service.create_payment()

        request = self.client.Code.create_qr_code.call_args.args[0]
        self.assertEqual(request["amount"], {"amount": 250, "currency": "JPY"})
        self.assertEqual(request["orderDescription"], "Test order")
        self.assertEqual(result["checkoutUrl"], "https://paypay.example/checkout")
        self.assertTrue(result["merchantPaymentId"])

    def test_create_payment_rejects_unsuccessful_paypay_response(self):
        self.client.Code.create_qr_code.return_value = {
            "resultInfo": {"code": "FAILED"},
            "data": {},
        }

        with self.assertRaises(PayPayAPIError):
            self.service.create_payment()

    def test_get_payment_returns_status(self):
        self.client.Code.get_payment_details.return_value = {
            "resultInfo": {"code": "SUCCESS"},
            "data": {"status": "COMPLETED", "paymentId": "paypay-payment"},
        }

        result = self.service.get_payment("merchant-payment-id")

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["paymentId"], "paypay-payment")


class PayPayHTTPTests(unittest.TestCase):
    def setUp(self):
        self.service = Mock()
        self.service.create_payment.return_value = {
            "merchantPaymentId": "8e03978e-40d5-43e8-bc93-6894a57f9324",
            "checkoutUrl": "https://paypay.example/checkout",
        }
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self.service)
        )
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_create_payment_endpoint(self):
        request = Request(f"{self.base_url}/api/payments", method="POST")

        with urlopen(request) as response:
            self.assertEqual(response.status, 201)
            self.assertEqual(json.load(response)["checkoutUrl"], "https://paypay.example/checkout")

    def test_invalid_payment_id_is_not_forwarded_to_sdk(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(f"{self.base_url}/api/payments/not-a-uuid")

        self.assertEqual(error.exception.code, 404)
        self.service.get_payment.assert_not_called()

    def test_create_payment_rejects_client_supplied_body(self):
        request = Request(
            f"{self.base_url}/api/payments",
            data=b'{"amount":1}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(HTTPError) as error:
            urlopen(request)

        self.assertEqual(error.exception.code, 400)
        self.service.create_payment.assert_not_called()


if __name__ == "__main__":
    unittest.main()
