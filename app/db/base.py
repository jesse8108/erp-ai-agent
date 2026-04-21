"""SQLAlchemy Base 类 - 所有 ORM model 继承这个。

W1 写 model 时会从这里 import。当前 W0 先占位，确保项目能跑。
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM model 的基类。"""

    pass
