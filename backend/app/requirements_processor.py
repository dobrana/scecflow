import json
from openai import OpenAI
import os
import re

client = OpenAI(
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

def extract_structured_info(transcript_text: str) -> dict:
    """
    Извлекает структурированную информацию из транскрипта
    """
    structured_info = {
        "meeting_info": {},
        "participants": [],
        "decisions": [],
        "conflicts": [],
        "requirements": {
            "goals": [],
            "functional": [],
            "non_functional": [],
            "introduction": [],
            "roles": [],
            "processes": []
        },
        "roles": [],
        "processes": []
    }
    
    # Извлекаем информацию о встрече
    meeting_pattern = r"ТРАНСКРИБАЦИЯ ВСТРЕЧИ №(\d+)\s*\nДата: (\d{2}\.\d{2}\.\d{4})\s*\nВремя: (\d{2}:\d{2}-\d{2}:\d{2})\s*\nУчастники: (\d+) человека\s*\nТема: (.+)"
    meeting_match = re.search(meeting_pattern, transcript_text, re.MULTILINE)
    if meeting_match:
        structured_info["meeting_info"] = {
            "meeting_number": meeting_match.group(1),
            "date": meeting_match.group(2),
            "time": meeting_match.group(3),
            "participants_count": meeting_match.group(4),
            "topic": meeting_match.group(5)
        }
    
    # Извлекаем участников и их роли
    participant_pattern = r"\[(\d{2}:\d{2})\] (\w+) \(([^)]+)\):"
    participants = re.findall(participant_pattern, transcript_text)
    for time, name, role in participants:
        if {"name": name, "role": role} not in structured_info["participants"]:
            structured_info["participants"].append({"name": name, "role": role})
    
    # Извлекаем решения (фразы с "решили", "определили", "согласились")
    decision_patterns = [
        r"[^.]*(?:решили|определили|согласились|утвердили)[^.]*",
        r"[^.]*(?:будет|должен|нужно)[^.]*",
        r"[^.]*(?:отлично|согласен|поддерживаю)[^.]*"
    ]
    for pattern in decision_patterns:
        decisions = re.findall(pattern, transcript_text, re.IGNORECASE)
        structured_info["decisions"].extend(decisions)
    
    # Извлекаем конфликты
    conflict_patterns = [
        r"[^.]*(?:конфликт|разногласие|спор|не согласен)[^.]*",
        r"[^.]*(?:это неправильно|абсолютно нет|не согласна)[^.]*"
    ]
    for pattern in conflict_patterns:
        conflicts = re.findall(pattern, transcript_text, re.IGNORECASE)
        structured_info["conflicts"].extend(conflicts)
    
    # Извлекаем роли и права
    role_patterns = [
        r"[^.]*(?:роль|права|доступ|может|должен)[^.]*",
        r"[^.]*(?:администратор|менеджер|инженер|логистик)[^.]*"
    ]
    for pattern in role_patterns:
        roles = re.findall(pattern, transcript_text, re.IGNORECASE)
        structured_info["roles"].extend(roles)
    
    return structured_info

def classify_requirements_with_llm(text: str) -> dict:
    """
    Универсальная классификация требований с помощью LLM
    """
    prompt = f"""
Ты — эксперт по анализу технических требований. Проанализируй следующий текст и классифицируй каждое предложение по релевантным категориям.

ВАЖНО: 
1. Не используй предопределенные категории - создавай их динамически на основе содержания
2. Названия категорий должны быть логичными и описательными
3. Группируй похожие требования в одни категории
4. Возвращай результат строго в JSON формате

Пример желаемого результата:
{{
  "пользовательские_функции": ["предложение 1", "предложение 2"],
  "технические_характеристики": ["предложение 3"],
  "интеграции": ["предложение 4"],
  "безопасность_и_доступ": ["предложение 5"]
}}

Текст для анализа:
{text}

Верни только JSON без дополнительного текста:
"""
    
    try:
        response = client.chat.completions.create(
            model="mistralai/mistral-7b-instruct:free",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        
        result = response.choices[0].message.content
        
        # Парсим JSON ответ
        try:
            classification = json.loads(result)
            print(f"LLM классификация: {list(classification.keys())}")
            return classification
        except json.JSONDecodeError:
            print(f"Ошибка парсинга JSON от LLM: {result}")
            return {}
            
    except Exception as e:
        print(f"Ошибка LLM классификации: {e}")
        return {}

def classify_requirements(text: str) -> dict:
    """
    Интеллектуальная классификация требований - пробует LLM, если не получается, возвращает базовую структуру
    """
    # Пробуем LLM классификацию
    llm_classification = classify_requirements_with_llm(text)
    
    if llm_classification:
        return llm_classification
    
    # Если LLM не сработал, возвращаем минимальную структуру
    print("LLM классификация не удалась, используется базовая структура")
    return {
        "general_requirements": [sentence.strip() for sentence in re.split(r'[.!?]+', text) if sentence.strip()]
    }

def analyze_topic_relevance(transcript_text: str, existing_document: dict) -> dict:
    """
    Анализирует релевантность транскрипции к существующему документу
    """
    # Извлекаем ключевые темы из существующего документа
    existing_topics = []
    relevant_sections = ['goals', 'introduction', 'functional_requirements', 'roles']
    
    for key, value in existing_document.items():
        if key in relevant_sections and isinstance(value, list):
            for item in value:
                text = item if isinstance(item, str) else (item.get('content', '') if isinstance(item, dict) else '')
                if text and len(text.strip()) > 10:  # Избегаем пустых строк
                    existing_topics.append(text)
        elif key in relevant_sections and isinstance(value, str) and len(value.strip()) > 10:
            existing_topics.append(value)
    
    # Если нет целей, используем контекст из заголовка или первой фразы
    if not existing_topics:
        existing_topics = ["система управления требованиями", "IT система", "техническое задание"]
    
    # Создаем промпт для анализа релевантности
    relevance_prompt = f"""
Проанализируй, относится ли эта транскрипция к существующему проекту или это обсуждение СОВЕРШЕННО ДРУГОГО проекта.

СУЩЕСТВУЮЩИЕ ЦЕЛИ ПРОЕКТА:
{existing_topics}

ТРАНСКРИПЦИЯ ДЛЯ АНАЛИЗА:
{transcript_text[:1000]}...

ПРАВИЛА АНАЛИЗА:
- Если транскрипция касается IT/программных систем, управления требованиями, процессов разработки - считай RELEVANT
- Если транскрипция про доставку еды, мобильные приложения, e-commerce, медицину - считай DIFFERENT_PROJECT
- "Система управления проектами" и "система управления требованиями" - это ОДНА область (управление в IT)
- Обсуждение ролей, процессов, технологий в контексте IT-систем - это RELEVANT

Ответь ТОЛЬКО одним словом:
- "RELEVANT" - если транскрипция относится к существующему проекту или смежной IT-области
- "DIFFERENT_PROJECT" - если это обсуждение совершенно другой отрасли/продукта

ОТВЕТ:"""

    try:
        response = client.chat.completions.create(
            model="mistralai/mistral-7b-instruct:free",
            messages=[{"role": "user", "content": relevance_prompt}],
            temperature=0.1,
            max_tokens=50
        )
        
        result = response.choices[0].message.content.strip().upper()
        print(f"Topic relevance analysis: {result}")
        
        return {
            "is_relevant": "RELEVANT" in result,
            "analysis": result
        }
    except Exception as e:
        print(f"Error in topic relevance analysis: {e}")
        return {"is_relevant": True, "analysis": "ERROR - assuming relevant"}

def process_transcript_with_llm(transcript_text: str, existing_document: dict) -> dict:
    
    # Сначала проверяем релевантность темы
    relevance_analysis = analyze_topic_relevance(transcript_text, existing_document)
    
    if not relevance_analysis["is_relevant"]:
        print("⚠️ ВНИМАНИЕ: Транскрипция относится к другому проекту! Обработка остановлена.")
        print(f"Анализ: {relevance_analysis['analysis']}")
        return existing_document
    
    print("✅ Транскрипция релевантна существующему проекту, продолжаем обработку...")
    
    # Сначала извлекаем структурированную информацию
    structured_info = extract_structured_info(transcript_text)
    
    # Классифицируем требования
    classified_requirements = classify_requirements(transcript_text)
    
    # Создаем улучшенный промпт
    prompt = f"""
Ты — опытный системный аналитик. Твоя задача - ДОПОЛНИТЬ техническое задание новой информацией из транскрипции, НЕ ЗАМЕНЯЯ существующий контент.

КРИТИЧЕСКИ ВАЖНО - ПРАВИЛА ДОПОЛНЕНИЯ:
1. НЕ УДАЛЯЙ и НЕ ЗАМЕНЯЙ существующую информацию в документе
2. АНАЛИЗИРУЙ существующий контент ПЕРЕД добавлением нового
3. ДОБАВЛЯЙ только ту информацию, которой НЕТ в существующем документе
4. Если информация ПОХОЖА на существующую - дополни её деталями, не заменяй полностью
5. ВСЕ НОВЫЕ элементы должны быть в формате: {{"status": "new", "content": "новая информация"}}

СТРАТЕГИЯ РАБОТЫ С РАЗДЕЛАМИ:
- Если раздел СУЩЕСТВУЕТ и СОДЕРЖИТ данные → ДОПОЛНИ его новыми элементами
- Если раздел ПУСТОЙ → заполни его новой информацией
- Если раздела НЕТ → создай новый раздел
- НИКОГДА не заменяй существующие элементы массива - только добавляй новые

СТРУКТУРИРОВАННАЯ ИНФОРМАЦИЯ ИЗ ТРАНСКРИПТА:
{json.dumps(structured_info, ensure_ascii=False, indent=2)}

КЛАССИФИЦИРОВАННЫЕ ТРЕБОВАНИЯ:
{json.dumps(classified_requirements, ensure_ascii=False, indent=2)}

СУЩЕСТВУЮЩИЙ ДОКУМЕНТ (НЕ ИЗМЕНЯЙ ЕГО СОДЕРЖИМОЕ):
{json.dumps(existing_document, ensure_ascii=False, indent=2)}

ТРАНСКРИБАЦИЯ (ИЗ НЕЁ ИЗВЛЕКАЙ НОВУЮ ИНФОРМАЦИЮ):
{transcript_text}

ПРАВИЛА ИНТЕЛЛЕКТУАЛЬНОГО ДОПОЛНЕНИЯ:
1. Анализируй ЧТО УЖЕ ЕСТЬ в существующем документе
2. Извлекай из транскрипции ТОЛЬКО ту информацию, которой там НЕТ
3. Если в транскрипции есть КОНФЛИКТЫ или РАЗНОГЛАСИЯ - добавь их в раздел "conflicts"
4. Группируй похожую информацию в СТАНДАРТНЫЕ разделы (НЕ создавай много мелких разделов!)
5. Содержимое на русском языке

ИСПОЛЬЗУЙ ТОЛЬКО ЭТИ СТАНДАРТНЫЕ РАЗДЕЛЫ:
- "goals" - цели и задачи проекта
- "roles" - роли и права доступа
- "functional_requirements" - функциональные требования
- "non_functional_requirements" - нефункциональные требования
- "security" - безопасность (НЕ создавай "safety_and_access")
- "budget" - бюджет и финансы (НЕ создавай "mvp_budget")
- "timeline" - сроки и дедлайны (НЕ создавай "deadlines") 
- "technical_requirements" - технологии и техтребования (НЕ создавай "technologies")
- "processes" - процессы и алгоритмы
- "conflicts" - конфликты и разногласия
- "participants" - участники проекта (НЕ создавай "team")
- "metadata" - метаданные

ПРИМЕРЫ ПРАВИЛЬНОГО ДОПОЛНЕНИЯ:

✅ ПРАВИЛЬНО - ДОПОЛНЕНИЕ РОЛЕЙ:
Существующие: ["Администратор - полные права", "Логистик - загрузка файлов"]
Новая информация: права инженера
Результат: [
  "Администратор - полные права", 
  "Логистик - загрузка файлов",
  {{"status": "new", "content": "Инженер - права на комментирование и просмотр ТЗ"}}
]

✅ ПРАВИЛЬНО - ДОПОЛНЕНИЕ ПРОЦЕССОВ:
Существующие: ["Создание документа", "Загрузка транскрипции"]
Новая информация: процесс согласования
Результат: [
  "Создание документа",
  "Загрузка транскрипции", 
  {{"status": "new", "content": "Процесс согласования изменений: предложение → рассмотрение → утверждение"}}
]

✅ ПРАВИЛЬНО - ДОБАВЛЕНИЕ КОНФЛИКТОВ:
Если в транскрипции есть разногласия - создай новый раздел:
"conflicts": [
  {{"status": "new", "content": "Разногласие по правам инженера: одни считают что нужны полные права на редактирование, другие - только на комментирование"}}
]

❌ НЕПРАВИЛЬНО - ЗАМЕНА:
НЕ заменяй существующие массивы полностью!
НЕ удаляй информацию которая уже была в документе!

ВЕРНИ ОБНОВЛЕННЫЙ JSON С ДОПОЛНЕНИЯМИ (не замененный!):
"""
    
    try:
        response = client.chat.completions.create(
            model="mistralai/mistral-7b-instruct:free",  # Используем Mistral через OpenRouter
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # Уменьшаем температуру для более стабильных результатов
            max_tokens=4000
        )
        updated_content_str = response.choices[0].message.content
        
        # Улучшенная обработка JSON
        parsed_document = parse_llm_response(updated_content_str, existing_document)
        
        # Отладочная информация
        print(f"LLM Response: {updated_content_str[:500]}...")
        print(f"Parsed document keys: {list(parsed_document.keys()) if isinstance(parsed_document, dict) else 'Not a dict'}")
        
        # Проверяем наличие элементов с status: "new"
        def check_for_new_elements(data, path=""):
            if isinstance(data, dict):
                if data.get("status") == "new":
                    print(f"Found new element at {path}: {data}")
                for key, value in data.items():
                    check_for_new_elements(value, f"{path}.{key}" if path else key)
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    check_for_new_elements(item, f"{path}[{i}]")
        
        check_for_new_elements(parsed_document)
        
        # Применяем умное слияние для предотвращения дублирования
        print("Applying smart content merging...")
        merged_document = {}
        
        # Создаем карту нормализованных ключей существующего документа
        existing_normalized = {}
        for key, value in existing_document.items():
            normalized_key = normalize_section_key(key)
            existing_normalized[normalized_key] = key
        
        for key, value in parsed_document.items():
            normalized_key = normalize_section_key(key)
            
            # Игнорируем ненужные разделы
            if should_ignore_section(key, value):
                print(f"Ignoring section {key} - too generic or short")
                continue
            
            # Проверяем, есть ли нормализованный ключ в существующем документе
            if normalized_key in existing_normalized:
                existing_key = existing_normalized[normalized_key]
                print(f"Merging {key} into existing {existing_key}")
                merged_document[existing_key] = smart_merge_content(existing_document[existing_key], value, existing_key)
            elif key in existing_document:
                # Обычное слияние для точных совпадений ключей
                merged_document[key] = smart_merge_content(existing_document[key], value, key)
            else:
                # Новые разделы добавляем как есть
                print(f"Adding new section: {key}")
                merged_document[key] = value
        
        # Добавляем разделы которые есть в старом документе, но нет в новом
        for key, value in existing_document.items():
            if key not in merged_document:
                merged_document[key] = value
        
        print(f"Merged document keys: {list(merged_document.keys())}")
        
        # Валидация структуры
        validation_result = validate_document_structure(merged_document)
        print(f"Document structure validation result: {validation_result}")
        print(f"Merged document structure: {list(merged_document.keys()) if isinstance(merged_document, dict) else 'Not a dict'}")
        
        if validation_result:
            print("Validation passed, returning merged document")
            return merged_document
        else:
            print("LLM вернул некорректную структуру документа")
            print(f"Missing required sections or structure invalid")
            print(f"Existing document structure: {list(existing_document.keys()) if isinstance(existing_document, dict) else 'Not a dict'}")
            return existing_document
            
    except Exception as e:
        print(f"Error processing with LLM: {e}")
        return existing_document

def parse_llm_response(response_text: str, existing_document: dict) -> dict:
    """
    Улучшенный парсинг ответа LLM
    """
    try:
        # Ищем JSON в ответе
        json_pattern = r'\{.*\}'
        json_matches = re.findall(json_pattern, response_text, re.DOTALL)
        
        if json_matches:
            # Пробуем каждый найденный JSON
            for json_str in json_matches:
                try:
                    parsed = json.loads(json_str)
                    if validate_document_structure(parsed):
                        return parsed
                except json.JSONDecodeError:
                    continue
        
        # Если не удалось найти валидный JSON, пытаемся исправить
        cleaned_response = clean_json_response(response_text)
        try:
            parsed = json.loads(cleaned_response)
            if validate_document_structure(parsed):
                return parsed
        except json.JSONDecodeError:
            pass
            
        return existing_document
        
    except Exception as e:
        print(f"Error parsing LLM response: {e}")
        return existing_document

def clean_json_response(response_text: str) -> str:
    """
    Очищает ответ LLM от лишнего текста
    """
    # Удаляем текст до первого {
    start = response_text.find('{')
    if start == -1:
        return "{}"
    
    # Удаляем текст после последнего }
    end = response_text.rfind('}') + 1
    if end == 0:
        return "{}"
    
    json_str = response_text[start:end]
    
    # Исправляем распространенные ошибки
    json_str = re.sub(r'```json\s*', '', json_str)
    json_str = re.sub(r'```\s*$', '', json_str)
    json_str = re.sub(r'^\s*```\s*', '', json_str)
    
    return json_str

def is_content_similar(text1: str, text2: str) -> bool:
    """
    Проверяет схожесть двух текстов для предотвращения дублирования
    """
    import difflib
    
    # Нормализуем текст
    norm1 = text1.lower().strip()
    norm2 = text2.lower().strip()
    
    # Если тексты идентичны
    if norm1 == norm2:
        return True
    
    # Проверяем схожесть (более 80% похожести считается дублированием)
    similarity = difflib.SequenceMatcher(None, norm1, norm2).ratio()
    return similarity > 0.8

def normalize_section_key(key):
    """
    Нормализует ключи разделов для предотвращения дублирования
    """
    key_mapping = {
        'safety_and_access': 'security',
        'safety and access': 'security',
        'mvp_budget': 'budget',
        'mvp budget': 'budget',
        'other_requirements': 'additional_requirements',
        'other requirements': 'additional_requirements',
        'team': 'participants',
        'technologies': 'technical_requirements',
        'deadlines': 'timeline'
    }
    
    normalized = key.lower().replace(' ', '_')
    return key_mapping.get(normalized, normalized)

def should_ignore_section(key, content):
    """
    Определяет нужно ли игнорировать раздел (слишком общий или бессмысленный)
    """
    ignore_sections = ['other_requirements', 'additional_info', 'misc']
    normalized_key = normalize_section_key(key)
    
    # Игнорируем слишком общие разделы
    if normalized_key in ignore_sections:
        return True
    
    # Игнорируем разделы с очень коротким или бессмысленным контентом
    if isinstance(content, list):
        total_length = sum(len(str(item)) for item in content)
        if total_length < 20:  # Слишком короткий контент
            return True
    
    return False

def smart_merge_content(existing_content, new_content, section_key=""):
    """
    Умное слияние контента без дублирования
    """
    print(f"Smart merging for section: {section_key}")
    
    # Нормализуем ключ раздела
    normalized_key = normalize_section_key(section_key)
    
    # Игнорируем ненужные разделы
    if should_ignore_section(section_key, new_content):
        print(f"Ignoring section {section_key} - too generic or short")
        return existing_content
    
    if not isinstance(existing_content, list):
        return new_content
    
    if not isinstance(new_content, list):
        return existing_content + [new_content] if existing_content else [new_content]
    
    # Собираем существующие тексты для проверки
    existing_texts = []
    for item in existing_content:
        if isinstance(item, dict) and 'content' in item:
            existing_texts.append(item['content'])
        elif isinstance(item, str):
            existing_texts.append(item)
    
    # Фильтруем новый контент от дубликатов
    filtered_new_content = []
    for new_item in new_content:
        new_text = ""
        if isinstance(new_item, dict) and 'content' in new_item:
            new_text = new_item['content']
        elif isinstance(new_item, str):
            new_text = new_item
        
        # Пропускаем слишком короткий или бессмысленный контент
        if len(new_text.strip()) < 10:
            print(f"Skipping too short content: {new_text}")
            continue
        
        # Проверяем на дублирование
        is_duplicate = False
        for existing_text in existing_texts:
            if is_content_similar(existing_text, new_text):
                print(f"Found duplicate content, skipping: {new_text[:100]}...")
                is_duplicate = True
                break
        
        if not is_duplicate:
            filtered_new_content.append(new_item)
            existing_texts.append(new_text)  # Добавляем в список для следующих проверок
    
    print(f"Added {len(filtered_new_content)} new items, skipped {len(new_content) - len(filtered_new_content)} duplicates")
    
    return existing_content + filtered_new_content

def validate_document_structure(document: dict) -> bool:
    """
    Проверяет корректность структуры документа
    """
    # Минимальные обязательные разделы
    required_sections = ["metadata"]
    
    # Желательные разделы (должен быть хотя бы один из основных)
    desirable_sections = [
        "introduction", "goals", "goals_objectives", 
        "functional_requirements", "non_functional_requirements",
        "system_overview", "executive_summary"
    ]
    
    print(f"Validating document structure...")
    print(f"Document type: {type(document)}")
    print(f"Document keys: {list(document.keys()) if isinstance(document, dict) else 'Not a dict'}")
    
    if not isinstance(document, dict):
        print("Document is not a dictionary")
        return False
    
    # Проверяем обязательные разделы
    missing_required = []
    for section in required_sections:
        if section not in document:
            missing_required.append(section)
    
    if missing_required:
        print(f"Missing required sections: {missing_required}")
        return False
    
    # Проверяем, что есть хотя бы один желательный раздел
    has_desirable_section = False
    found_desirable = []
    for section in desirable_sections:
        if section in document:
            has_desirable_section = True
            found_desirable.append(section)
    
    print(f"Found desirable sections: {found_desirable}")
    
    if not has_desirable_section:
        print("No desirable sections found")
        return False
    
    print("Document structure validation passed")
    return True

def accept_changes_in_document(document_content: dict) -> dict:
    """
    Принимает все изменения в документе - убирает статус "new" и оставляет только content
    """
    def recursive_clean(data):
        if isinstance(data, dict):
            if data.get("status") == "new" and "content" in data:
                return data["content"]
            return {k: recursive_clean(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [recursive_clean(item) for item in data]
        else:
            return data
    return recursive_clean(document_content)

def analyze_document_with_llm(document_content: dict) -> str:
    prompt = f"""
Ты — опытный менеджер проектов и системный аналитик. Проанализируй следующее техническое задание в формате JSON на предмет потенциальных рисков, противоречий и неполноты.

Твоя задача:
1. Внимательно изучи все разделы документа.
2. Выяви возможные конфликты между требованиями.
3. Определи "узкие места" или не до конца проработанные моменты.
4. Укажи на потенциальные технические или бизнес-риски.
5. Дай краткие и четкие рекомендации по каждому найденному пункту.

Ответ должен быть в формате маркированного списка. Если проблем не найдено, напиши "Противоречий и рисков не обнаружено".

Документ для анализа:
{json.dumps(document_content, ensure_ascii=False, indent=2)}

Анализ:
"""
    try:
        response = client.chat.completions.create(
            model="mistralai/mistral-7b-instruct:free",  # Используем Mistral через OpenRouter
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error analyzing with LLM: {e}")
        raise ValueError("Ошибка при анализе документа с помощью AI.")