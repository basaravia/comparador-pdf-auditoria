class GatewayError(Exception):
    """Base para errores del ModelGateway.

    El pipeline L5 (§4.11) captura estos errores y los traduce a
    ChangeUnit.analysis.status = "failed" — nunca a contenido inventado.
    """


class RoleNotConfiguredError(GatewayError):
    """El rol lógico pedido (p.ej. 'analista_texto') no está en models.yaml."""


class ModelCallError(GatewayError):
    """La llamada al provider falló (red, timeout, respuesta inválida)."""
