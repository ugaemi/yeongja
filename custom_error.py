class CrawlingError(Exception):
    message = "네이버로부터 데이터를 가져올 수 없습니다."

    def __init__(self, expression, message):
        self.expression = expression
        self.message = message
