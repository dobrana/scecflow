import json
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from io import BytesIO

from .database import supabase
from .auth import get_current_user, User
from .models import DocumentCreate, DocumentUpdate, ChangePasswordRequest, AnalysisResponse, AnalysisHistoryCreate, AnalysisHistoryResponse, FeedbackCreate, FeedbackResponse
from . import requirements_processor

app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",
        "https://*.vercel.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Document Templates ---
TECHNICAL_SPEC_TEMPLATE = {
  "metadata": { "title": "Новое техническое задание", "version": "1.0", "date": "" },
  "introduction": { "title": "Введение", "content": "" },
  "goals": { "title": "Цели и задачи", "content": [] },
  "functional_requirements": { "title": "Функциональные требования", "content": {} },
  "non_functional_requirements": { "title": "Нефункциональные требования", "content": {} }
}
USER_STORIES_TEMPLATE = {
  "metadata": { "title": "Пользовательские истории", "version": "1.0", "product_owner": "" },
  "epics": {
    "epic_1": { "title": "Основной Эпик", "description": "", "user_stories": {} }
  }
}

# --- API Endpoints ---

@app.get("/documents")
def get_documents(current_user: User = Depends(get_current_user)):
    response = supabase.table("requirement_documents").select("id, title, document_type, updated_at").eq("user_id", current_user.id).order("updated_at", desc=True).execute()
    return response.data

@app.post("/documents")
def create_document(doc: DocumentCreate, current_user: User = Depends(get_current_user)):
    # Check document limit (max 3 for free tier)
    count_response = supabase.rpc('get_user_document_count', {'p_user_id': current_user.id}).execute()
    if count_response.data >= 3:
        raise HTTPException(status_code=403, detail="Достигнут лимит в 3 документа на бесплатном тарифе.")

    template = TECHNICAL_SPEC_TEMPLATE if doc.document_type == 'technical_spec' else USER_STORIES_TEMPLATE
    template['metadata']['title'] = doc.title

    new_doc = {
        "user_id": current_user.id,
        "title": doc.title,
        "document_type": doc.document_type,
        "content": template
    }
    response = supabase.table("requirement_documents").insert(new_doc).execute()
    return response.data[0]

@app.get("/documents/{doc_id}")
def get_document(doc_id: str, current_user: User = Depends(get_current_user)):
    response = supabase.table("requirement_documents").select("*").eq("id", doc_id).eq("user_id", current_user.id).single().execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return response.data

@app.put("/documents/{doc_id}")
def update_document(doc_id: str, doc_update: DocumentUpdate, current_user: User = Depends(get_current_user)):
    response = supabase.table("requirement_documents").update({
        "title": doc_update.title,
        "content": doc_update.content,
        "updated_at": "now()"
    }).eq("id", doc_id).eq("user_id", current_user.id).execute()
    return response.data

@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str, current_user: User = Depends(get_current_user)):
    response = supabase.table("requirement_documents").delete().eq("id", doc_id).eq("user_id", current_user.id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return {"message": "Документ успешно удален"}

@app.post("/documents/{doc_id}/process")
async def process_transcription(doc_id: str, files: List[UploadFile] = File(...), current_user: User = Depends(get_current_user)):
    doc_response = supabase.table("requirement_documents").select("content").eq("id", doc_id).eq("user_id", current_user.id).single().execute()
    if not doc_response.data:
        raise HTTPException(status_code=404, detail="Документ не найден")

    full_transcript = ""
    for file in files:
        try:
            file_content = await file.read()
            
            # Обработка разных форматов файлов
            if file.filename.lower().endswith('.txt'):
                # Текстовые файлы
                text_content = file_content.decode('utf-8', errors='ignore')
                full_transcript += text_content + "\n\n"
                
            elif file.filename.lower().endswith('.docx'):
                # DOCX файлы
                try:
                    from docx import Document
                    doc = Document(BytesIO(file_content))
                    text_content = ""
                    for paragraph in doc.paragraphs:
                        text_content += paragraph.text + "\n"
                    full_transcript += text_content + "\n\n"
                except ImportError:
                    raise HTTPException(status_code=400, detail="Для обработки .docx файлов требуется установить python-docx")
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"Не удалось обработать .docx файл {file.filename}: {e}")
                    
            elif file.filename.lower().endswith('.doc'):
                # DOC файлы (старый формат)
                raise HTTPException(status_code=400, detail=f"Формат .doc не поддерживается. Конвертируйте файл в .docx или .txt")
                
            else:
                raise HTTPException(status_code=400, detail=f"Формат файла {file.filename} не поддерживается. Используйте .txt или .docx файлы.")
                
        except Exception as e:
            if "HTTPException" in str(type(e)):
                raise e
            raise HTTPException(status_code=400, detail=f"Не удалось обработать файл {file.filename}: {e}")

    if not full_transcript.strip():
        raise HTTPException(status_code=400, detail="Загруженные файлы не содержат текста.")

    try:
        print(f"Processing transcript for document {doc_id}")
        print(f"Original document content keys: {list(doc_response.data['content'].keys()) if isinstance(doc_response.data['content'], dict) else 'Not a dict'}")
        
        updated_content = requirements_processor.process_transcript_with_llm(full_transcript, doc_response.data['content'])
        
        print(f"Updated content keys: {list(updated_content.keys()) if isinstance(updated_content, dict) else 'Not a dict'}")
        print(f"Content changed: {updated_content != doc_response.data['content']}")
        
        # Если контент не изменился, возможно транскрипция была нерелевантной
        if updated_content == doc_response.data['content']:
            print("⚠️ Документ не был изменен - возможно транскрипция нерелевантна")
            # Возвращаем документ без обновления в БД
            return doc_response.data
        
        update_response = supabase.table("requirement_documents").update({"content": updated_content, "updated_at": "now()"}).eq("id", doc_id).execute()
        
        print(f"Database update response: {len(update_response.data) if update_response.data else 0} rows affected")
        print(f"Returning document with keys: {list(update_response.data[0]['content'].keys()) if update_response.data and isinstance(update_response.data[0].get('content'), dict) else 'No content or not dict'}")
        
        return update_response.data[0]
    except ValueError as e:
        print(f"ValueError in process_transcription: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f"Unexpected error in process_transcription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/documents/{doc_id}/accept")
def accept_changes(doc_id: str, current_user: User = Depends(get_current_user)):
    doc_response = supabase.table("requirement_documents").select("content").eq("id", doc_id).eq("user_id", current_user.id).single().execute()
    if not doc_response.data:
        raise HTTPException(status_code=404, detail="Документ не найден")

    cleaned_content = requirements_processor.accept_changes_in_document(doc_response.data['content'])
    update_response = supabase.table("requirement_documents").update({"content": cleaned_content, "version": doc_response.data.get('version', 1) + 1, "updated_at": "now()"}).eq("id", doc_id).execute()
    return update_response.data[0]

@app.post("/documents/{doc_id}/analyze", response_model=AnalysisResponse)
def analyze_document(doc_id: str, current_user: User = Depends(get_current_user)):
    doc_response = supabase.table("requirement_documents").select("content").eq("id", doc_id).eq("user_id", current_user.id).single().execute()
    if not doc_response.data:
        raise HTTPException(status_code=404, detail="Документ не найден")

    try:
        # Сохраняем запрос пользователя в историю
        user_query = "Анализ документа"
        supabase.table("analysis_history").insert({
            "document_id": doc_id,
            "message_type": "user_query",
            "content": user_query
        }).execute()
        
        analysis_result = requirements_processor.analyze_document_with_llm(doc_response.data['content'])
        
        # Сохраняем ответ ИИ в историю
        supabase.table("analysis_history").insert({
            "document_id": doc_id,
            "message_type": "ai_response",
            "content": analysis_result
        }).execute()
        
        return AnalysisResponse(analysis=analysis_result)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{doc_id}/analysis-history", response_model=AnalysisHistoryResponse)
def get_analysis_history(doc_id: str, current_user: User = Depends(get_current_user)):
    # Проверяем, что документ принадлежит пользователю
    doc_response = supabase.table("requirement_documents").select("id").eq("id", doc_id).eq("user_id", current_user.id).single().execute()
    if not doc_response.data:
        raise HTTPException(status_code=404, detail="Документ не найден")
    
    # Получаем историю анализа
    history_response = supabase.table("analysis_history").select("*").eq("document_id", doc_id).order("created_at", desc=False).execute()
    
    return AnalysisHistoryResponse(history=history_response.data)

@app.post("/documents/{doc_id}/feedback", response_model=FeedbackResponse)
def submit_feedback(doc_id: str, feedback: FeedbackCreate, current_user: User = Depends(get_current_user)):
    # Проверяем, что документ принадлежит пользователю
    doc_response = supabase.table("requirement_documents").select("id").eq("id", doc_id).eq("user_id", current_user.id).single().execute()
    if not doc_response.data:
        raise HTTPException(status_code=404, detail="Документ не найден")
    
    # Сохраняем отзыв
    feedback_response = supabase.table("feedback").insert({
        "user_id": current_user.id,
        "document_id": doc_id,
        "content": feedback.content,
        "feedback_type": feedback.feedback_type
    }).execute()
    
    return FeedbackResponse(message="Отзыв успешно отправлен")

# --- User Management ---

@app.post("/user/change-password")
def change_password(request: ChangePasswordRequest, current_user: User = Depends(get_current_user)):
    response = supabase.auth.admin.update_user_by_id(current_user.id, {"password": request.new_password})
    if response.user is None:
        raise HTTPException(status_code=400, detail="Не удалось изменить пароль.")
    return {"message": "Пароль успешно изменен."}

@app.delete("/user/me")
def delete_account(current_user: User = Depends(get_current_user)):
    response = supabase.auth.admin.delete_user(current_user.id)
    if response.user is None:
        raise HTTPException(status_code=400, detail="Не удалось удалить аккаунт.")
    return {"message": "Аккаунт и все данные успешно удалены."}

# --- Monetization Hypothesis ---

@app.post("/pro-plan-request")
def pro_plan_request(current_user: User = Depends(get_current_user)):
    supabase.table("pro_plan_requests").insert({"user_id": current_user.id}).execute()
    return {"message": "Заявка принята"}