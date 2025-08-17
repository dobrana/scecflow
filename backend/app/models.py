from pydantic import BaseModel, Field
from typing import Literal

# Эта модель используется при создании нового документа.
# Frontend отправляет только название и тип, остальное генерируется на сервере.
class DocumentCreate(BaseModel):
    title: str
    document_type: Literal['technical_spec', 'user_stories']

# Эта модель используется при сохранении изменений в существующем документе.
# Frontend отправляет обновленное название и всё содержимое документа в формате JSON.
class DocumentUpdate(BaseModel):
    title: str
    content: dict

# Эта модель используется для запроса на смену пароля.
# Мы добавляем валидацию, чтобы пароль был не короче 6 символов.
class ChangePasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6)

# Эта модель используется для ответа от эндпоинта анализа документа.
# Она гарантирует, что ответ всегда будет иметь предсказуемую структуру.
class AnalysisResponse(BaseModel):
    analysis: str

# Модели для истории анализа
class AnalysisHistoryCreate(BaseModel):
    document_id: str
    message_type: Literal['user_query', 'ai_response']
    content: str

class AnalysisHistoryItem(BaseModel):
    id: str
    document_id: str
    message_type: Literal['user_query', 'ai_response']
    content: str
    created_at: str

class AnalysisHistoryResponse(BaseModel):
    history: list[AnalysisHistoryItem]

# Модели для системы отзывов
class FeedbackCreate(BaseModel):
    document_id: str
    content: str
    feedback_type: Literal['general', 'bug_report', 'feature_request', 'analysis_quality'] = 'general'

class FeedbackItem(BaseModel):
    id: str
    user_id: str
    document_id: str
    content: str
    feedback_type: str
    created_at: str

class FeedbackResponse(BaseModel):
    message: str