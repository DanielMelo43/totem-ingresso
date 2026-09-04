from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from sqlalchemy.orm import Session

from ..config import get_settings
from ..errors import AppError
from ..models import ServiceCircuit, utc_now


settings = get_settings()


class PaymentGateway:
    """Adaptador do gateway. O simulador pode ser trocado sem expor detalhes ao controller."""

    service_name = "payment_gateway"

    def _send(self, order_id: str, amount: str, method: str) -> dict:
        return {"approved": True, "provider_reference": f"SIM-{order_id[:8]}"}

    def charge(self, db: Session, order_id: str, amount: str, method: str) -> dict:
        circuit = db.get(ServiceCircuit, self.service_name)
        now = utc_now()
        if circuit and circuit.state == "open":
            elapsed = (now - circuit.opened_at).total_seconds() if circuit.opened_at else 0
            if elapsed < settings.circuit_recovery_seconds:
                raise AppError(503, "PAGAMENTO_INDISPONIVEL", "Pagamento indisponível no momento. Tente novamente.")
            circuit.state = "half_open"
            db.commit()

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._send, order_id, amount, method)
        try:
            result = future.result(timeout=settings.payment_timeout_seconds)
        except FutureTimeout:
            future.cancel()
            self._record_failure(db)
            raise AppError(504, "TIMEOUT_GATEWAY", "O pagamento ainda está sendo verificado. Consulte o status do pedido.")
        except Exception:
            self._record_failure(db)
            raise AppError(502, "FALHA_GATEWAY", "Não foi possível contatar o serviço de pagamento.")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        self._record_success(db)
        return result

    def _record_failure(self, db: Session) -> None:
        circuit = db.get(ServiceCircuit, self.service_name) or ServiceCircuit(service=self.service_name)
        if circuit not in db:
            db.add(circuit)
        circuit.failures += 1
        if circuit.failures >= settings.circuit_failure_threshold:
            circuit.state = "open"
            circuit.opened_at = utc_now()
        db.commit()

    def _record_success(self, db: Session) -> None:
        circuit = db.get(ServiceCircuit, self.service_name)
        if circuit:
            circuit.state = "closed"
            circuit.failures = 0
            circuit.opened_at = None
            db.commit()


payment_gateway = PaymentGateway()

