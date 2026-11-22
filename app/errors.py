class AppError(Exception):
    """Бизнес-ошибка, которую можно показать пользователю."""

    status_code = 400

    def __init__(self, code: str, message: str, status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class InsufficientFunds(AppError):
    def __init__(self) -> None:
        super().__init__("insufficient_funds", "Недостаточно звёзд на балансе")


class NotFound(AppError):
    status_code = 404

    def __init__(self, what: str = "Объект") -> None:
        super().__init__("not_found", f"{what} не найден")


class Forbidden(AppError):
    status_code = 403

    def __init__(self, message: str = "Доступ запрещён") -> None:
        super().__init__("forbidden", message)
