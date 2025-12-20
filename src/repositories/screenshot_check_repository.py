from datetime import datetime
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.screenshot_check import ScreenshotCheck


class ScreenshotCheckRepository:
    """Репозиторий для работы с проверками скриншотов."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_group_id(self, group_id: int) -> Optional[ScreenshotCheck]:
        """Получить запись проверки скриншота по ID группы."""
        result = await self.session.execute(
            select(ScreenshotCheck).where(ScreenshotCheck.group_id == group_id)
        )
        return result.scalar_one_or_none()
    
    async def update_or_create(self, group_id: int, screenshot_time: datetime) -> ScreenshotCheck:
        """Обновить или создать запись о времени последнего скриншота."""
        check = await self.get_by_group_id(group_id)
        
        if check:
            check.last_screenshot_time = screenshot_time
            await self.session.flush()
            return check
        else:
            check = ScreenshotCheck(
                group_id=group_id,
                last_screenshot_time=screenshot_time
            )
            self.session.add(check)
            await self.session.flush()
            return check
    
    async def get_all(self) -> list[ScreenshotCheck]:
        """Получить все записи проверок скриншотов."""
        result = await self.session.execute(select(ScreenshotCheck))
        return list(result.scalars().all())

