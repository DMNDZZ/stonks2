# google_sheets.py
import gspread
from config import *
import time
from datetime import datetime

class GoogleSheetsManager:
    def __init__(self):
        self.gc = None
        self.spreadsheet = None
        self.max_retries = 3
        self.retry_delay = 5
        self.connect_with_retry()
        self.initialize_sheets()
    
    def initialize_sheets(self):
        """Инициализация всех необходимых листов"""
        try:
            if self.gc and self.spreadsheet:
                # Инициализируем все листы
                self.inventory_sheet = self.spreadsheet.worksheet(INVENTORY_SHEET)
                self.prices_sheet = self.spreadsheet.worksheet(PRICES_SHEET)
                self.contracts_sheet = self.spreadsheet.worksheet(CONTRACTS_SHEET)
                self.rentals_sheet = self.spreadsheet.worksheet(RENTALS_SHEET)
                self.clients_sheet = self.spreadsheet.worksheet(CLIENTS_SHEET)
                
                print("✅ Все листы инициализированы:")
                print(f"   - {INVENTORY_SHEET}")
                print(f"   - {PRICES_SHEET}")
                print(f"   - {CONTRACTS_SHEET}")
                print(f"   - {RENTALS_SHEET}")
                print(f"   - {CLIENTS_SHEET}")
            else:
                print("❌ Не удалось инициализировать листы - нет подключения к таблице")
                self.inventory_sheet = None
                self.prices_sheet = None
                self.contracts_sheet = None
                self.rentals_sheet = None
                self.clients_sheet = None
                
        except Exception as e:
            print(f"❌ Ошибка инициализации листов: {e}")
            # Устанавливаем все листы в None при ошибке
            self.inventory_sheet = None
            self.prices_sheet = None
            self.contracts_sheet = None
            self.rentals_sheet = None
            self.clients_sheet = None

    def connect_with_retry(self):
        """Подключение с повторными попытками"""
        for attempt in range(self.max_retries):
            try:
                print(f"🔄 Попытка подключения {attempt + 1}/{self.max_retries}...")
                
                credentials_info = {
                    "type": GOOGLE_TYPE,
                    "project_id": GOOGLE_PROJECT_ID,
                    "private_key_id": GOOGLE_PRIVATE_KEY_ID,
                    "private_key": GOOGLE_PRIVATE_KEY,
                    "client_email": GOOGLE_CLIENT_EMAIL,
                    "client_id": GOOGLE_CLIENT_ID,
                    "auth_uri": GOOGLE_AUTH_URI,
                    "token_uri": GOOGLE_TOKEN_URI,
                    "auth_provider_x509_cert_url": GOOGLE_AUTH_PROVIDER_X509_CERT_URL,
                    "client_x509_cert_url": GOOGLE_CLIENT_X509_CERT_URL,
                    "universe_domain": GOOGLE_UNIVERSE_DOMAIN,
                }
                missing_fields = [
                    field for field in ("project_id", "private_key_id", "private_key", "client_email", "client_id")
                    if not credentials_info[field]
                ]
                if missing_fields:
                    raise RuntimeError(
                        "Google service account fields are missing: " + ", ".join(missing_fields)
                    )
                self.gc = gspread.service_account_from_dict(credentials_info)
                self.spreadsheet = self.gc.open(SPREADSHEET_NAME)
                
                print("✅ Успешное подключение к Google Sheets!")
                
                if self.check_sheets_exist():
                    return
                else:
                    print("❌ Не все листы найдены")
                    return
                    
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                if attempt < self.max_retries - 1:
                    print(f"⏳ Ожидание {self.retry_delay} секунд...")
                    time.sleep(self.retry_delay)
                else:
                    break

    def check_sheets_exist(self):
        """Проверка существования листов"""
        try:
            sheet_titles = [sheet.title for sheet in self.spreadsheet.worksheets()]
            required_sheets = [INVENTORY_SHEET, PRICES_SHEET, CONTRACTS_SHEET, RENTALS_SHEET, CLIENTS_SHEET]
            
            print("📋 Поиск листов в таблице...")
            
            all_sheets_found = True
            for sheet_name in required_sheets:
                if sheet_name in sheet_titles:
                    print(f"✅ Найден лист: {sheet_name}")
                else:
                    print(f"❌ Лист не найден: {sheet_name}")
                    print(f"   Доступные листы: {sheet_titles}")
                    all_sheets_found = False
            
            return all_sheets_found
            
        except Exception as e:
            print(f"❌ Ошибка проверки листов: {e}")
            return False

    def normalize_phone(self, phone: str) -> str:
        """Нормализация номера телефона для сравнения"""
        if not phone:
            return ""
        
        # Убираем все нецифровые символы
        digits = ''.join(filter(str.isdigit, phone))
        
        # Если номер начинается с 7 или 8, оставляем 11 цифр
        if digits.startswith('7') or digits.startswith('8'):
            if len(digits) == 11:
                return digits[1:]  # Убираем 7 или 8
            elif len(digits) == 10:
                return digits
        
        # Если номер начинается с 9, предполагаем что это 10 цифр
        if digits.startswith('9') and len(digits) == 10:
            return digits
        
        # Для других форматов возвращаем как есть
        return digits

    def generate_contract_number(self):
        """Оптимизированная генерация уникального ID договора"""
        try:
            if not self.clients_sheet:
                print("❌ Лист клиентов не инициализирован")
                return "1001"
                
            # Используем более эффективный метод для больших баз
            # Получаем только нужный столбец вместо всех данных
            all_contract_numbers = []
            
            # Определяем индекс столбца с ID договора один раз
            headers = self.clients_sheet.row_values(1)
            contract_column_index = -1
            
            for i, header in enumerate(headers):
                header_lower = header.lower()
                if 'договор' in header_lower or 'id' in header_lower:
                    contract_column_index = i
                    break
            
            if contract_column_index == -1:
                contract_column_index = 4  # fallback
            
            # Получаем только значения нужного столбца (более эффективно)
            column_values = self.clients_sheet.col_values(contract_column_index + 1)  # +1 т.к. 1-based
            print(f"🔍 Найдено {len(column_values)} значений в столбце ID договора")
            
            # Пропускаем заголовок
            if column_values:
                column_values = column_values[1:]
            
            max_contract_number = 1000
            
            for contract_num in column_values:
                if contract_num and str(contract_num).strip():
                    clean_num = str(contract_num).strip().replace(' ', '').replace('.', '')
                    if clean_num.isdigit():
                        num = int(clean_num)
                        if num > max_contract_number:
                            max_contract_number = num
            
            next_contract_number = max_contract_number + 1
            print(f"✅ Сгенерирован ID договора: {next_contract_number}")
            return str(next_contract_number)
            
        except Exception as e:
            print(f"❌ Ошибка генерации ID договора: {e}")
            import traceback
            traceback.print_exc()
            return "1001"

    def generate_act_number(self):
        """Генерация следующего номера акта (автоинкремент)"""
        try:
            if not self.contracts_sheet:
                print("❌ Лист договоров не инициализирован")
                return "1000"
            
            # Получаем все данные чтобы найти столбец с номерами актов
            all_data = self.contracts_sheet.get_all_values()
            
            if len(all_data) < 2:
                return "1000"  # Первая запись
            
            headers = all_data[0]
            data_rows = all_data[1:]
            
            # Ищем индекс столбца с номером акта (второй столбец)
            act_column_index = 1  # Второй столбец (индекс 1)
            
            # Дополнительная проверка по заголовку
            for i, header in enumerate(headers):
                if 'акт' in header.lower() or 'номер' in header.lower():
                    act_column_index = i
                    break
            
            print(f"🔍 Индекс столбца акта: {act_column_index}")
            print(f"🔍 Заголовки: {headers}")
            
            max_act_number = 1
            
            for i, row in enumerate(data_rows):
                if act_column_index < len(row):
                    act_number = row[act_column_index]
                    print(f"🔍 Строка {i+2}: номер акта = '{act_number}'")
                    if act_number and act_number.strip().replace(' ', '').isdigit():
                        num = int(act_number.strip().replace(' ', ''))
                        if num > max_act_number:
                            max_act_number = num
            
            next_act_number = max_act_number + 1
            print(f"✅ Сгенерирован номер акта: {next_act_number}")
            return str(next_act_number)
            
        except Exception as e:
            print(f"❌ Ошибка генерации номера акта: {e}")
            import traceback
            traceback.print_exc()
            return "1000"

    def find_client_by_phone(self, phone: str):
        """Поиск клиента по номеру телефона"""
        try:
            if not self.clients_sheet:
                print("❌ Лист клиентов не инициализирован")
                return None
                
            clients = self.clients_sheet.get_all_records()
            search_phone = self.normalize_phone(phone)
            
            print(f"🔍 Поиск клиента по телефону:")
            print(f"   Исходный: '{phone}'")
            print(f"   Нормализованный: '{search_phone}'")
            print(f"📋 Всего клиентов в базе: {len(clients)}")
            
            for i, client in enumerate(clients):
                client_phone_raw = str(client.get('Номер телефона', ''))
                client_phone = self.normalize_phone(client_phone_raw)
                
                print(f"   Клиент {i+1}: '{client_phone_raw}' -> '{client_phone}'")
                
                if client_phone == search_phone:
                    print(f"✅ Клиент найден: {client.get('ФИО', '')}")
                    return client
            
            print("❌ Клиент не найден")
            return None
            
        except Exception as e:
            print(f"❌ Ошибка поиска клиента: {e}")
            return None
    
    def debug_number_generation(self):
        """Отладочная информация о генерации номеров"""
        try:
            print("🔍 ОТЛАДКА ГЕНЕРАЦИИ НОМЕРОВ:")
            
            # Проверяем клиентов
            if self.clients_sheet:
                clients_data = self.clients_sheet.get_all_values()
                print(f"📋 Клиентов всего: {len(clients_data) - 1}")
                if len(clients_data) > 1:
                    print("📝 ID договоров в базе клиентов:")
                    headers = clients_data[0]
                    for i, row in enumerate(clients_data[1:], start=2):
                        print(f"   Строка {i}: {row}")
            
            # Проверяем договоры
            if self.contracts_sheet:
                contracts_data = self.contracts_sheet.get_all_values()
                print(f"📄 Договоров всего: {len(contracts_data) - 1}")
                if len(contracts_data) > 1:
                    print("📝 Номера актов в базе договоров:")
                    headers = contracts_data[0]
                    for i, row in enumerate(contracts_data[1:], start=2):
                        print(f"   Строка {i}: {row}")
                        
        except Exception as e:
            print(f"❌ Ошибка отладки: {e}")

    def debug_clients_structure(self):
        """Отладочная информация о структуре базы клиентов"""
        try:
            if not self.clients_sheet:
                print("❌ Лист клиентов не инициализирован")
                return
                
            all_data = self.clients_sheet.get_all_values()
            
            if not all_data:
                print("ℹ️ Таблица клиентов пуста")
                return
            
            print("🔍 СТРУКТУРА БАЗЫ КЛИЕНТОВ:")
            print(f"📋 Заголовки: {all_data[0]}")
            print(f"📊 Всего записей: {len(all_data) - 1}")
            
            if len(all_data) > 1:
                print("📝 Первые 3 записи:")
                for i, row in enumerate(all_data[1:4], start=1):
                    print(f"   {i}. {row}")
                    
        except Exception as e:
            print(f"❌ Ошибка отладки структуры клиентов: {e}")

    def save_client(self, client_data):
        """Сохранение нового клиента в базу"""
        try:
            if not self.clients_sheet:
                print("❌ Лист клиентов не инициализирован")
                return False
                
            # Подготавливаем данные для записи
            client_row = [
                client_data.get('Дата', ''),
                client_data.get('ФИО', ''),
                client_data.get('Паспорт', ''),
                client_data.get('Телефон', ''),
                client_data.get('ID_договора', ''),  # ID договора генерируется заранее
                'Нет'
            ]
            
            self.clients_sheet.append_row(client_row)
            print(f"✅ Клиент {client_data.get('ФИО')} сохранен в базу с ID договора: {client_data.get('ID_договора', '')}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка сохранения клиента: {e}")
            return False

    def is_contract_signed(self, phone: str) -> bool:
        """Проверяет, подписан ли договор клиентом"""
        try:
            client = self.find_client_by_phone(phone)
            if client:
                signed_status = client.get('Подписан', '').lower().strip()
                print(f"🔍 Статус подписания для {phone}: '{signed_status}'")
                return signed_status == 'да'
            return False
        except Exception as e:
            print(f"❌ Ошибка проверки подписания договора: {e}")
            return False

    def mark_contract_signed(self, phone: str):
        """Отмечает договор как подписанный"""
        try:
            if not self.clients_sheet:
                print("❌ Лист клиентов не инициализирован")
                return False
                
            # Находим строку клиента
            all_data = self.clients_sheet.get_all_values()
            headers = all_data[0]
            
            # Ищем индекс столбца "Подписан"
            signed_column_index = -1
            phone_column_index = -1
            
            for i, header in enumerate(headers):
                if 'подписан' in header.lower():
                    signed_column_index = i
                elif 'телефон' in header.lower():
                    phone_column_index = i
            
            if signed_column_index == -1:
                print("❌ Не найден столбец 'Подписан'")
                return False
                
            # Ищем строку с телефоном
            for i, row in enumerate(all_data[1:], start=2):
                if phone_column_index < len(row) and self.normalize_phone(row[phone_column_index]) == self.normalize_phone(phone):
                    # Обновляем статус
                    self.clients_sheet.update_cell(i, signed_column_index + 1, 'Да')  # +1 т.к. gspread 1-based
                    print(f"✅ Договор отмечен как подписанный для телефона: {phone}")
                    return True
            
            print(f"❌ Клиент с телефоном {phone} не найден")
            return False
        
        except Exception as e:
            print(f"❌ Ошибка отметки договора как подписанного: {e}")
            return False

    def get_client_info_for_contract(self, contract_number: str):
        """Получение информации о клиенте для договора"""
        try:
            if not self.clients_sheet:
                print("❌ Лист клиентов не инициализирован")
                return None
                
            clients = self.clients_sheet.get_all_records()
            
            for client in clients:
                if client.get('ID договора') == contract_number:
                    return {
                        'ФИО': client.get('ФИО', ''),
                        'Телефон': client.get('Номер телефона', ''),
                        'Паспорт': client.get('Серия и номер паспорта', '')
                    }
            
            return None
            
        except Exception as e:
            print(f"❌ Ошибка поиска клиента для договора: {e}")
            return None

    def create_rental_records(self, contract_number, equipment_list):
        """Создание записей в таблице Аренды"""
        try:
            if not self.rentals_sheet:
                print("❌ Лист аренд не инициализирован")
                return
                
            records = []
            for equipment in equipment_list:
                record = [
                    contract_number,
                    equipment.get('type', ''),
                    equipment.get('brand', ''),
                    equipment.get('size', ''),
                    equipment.get('original_data', {}).get('Штрихкод', ''),
                    'активно',  # статус
                    ''  # время возврата
                ]
                records.append(record)
            
            if records:
                self.rentals_sheet.append_rows(records)
                print(f"✅ Создано {len(records)} записей аренды для договора {contract_number}")
            
        except Exception as e:
            print(f"❌ Ошибка создания записей аренды: {e}")
    
    def find_active_rentals(self, phone: str):
        """Поиск активных аренд по телефону (все оборудование сразу)"""
        try:
            if not self.contracts_sheet or not self.rentals_sheet:
                print("❌ Листы договоров или аренд не инициализированы")
                return []
                
            # Получаем все договоры с этим телефоном
            contracts = self.contracts_sheet.get_all_records()
            active_contracts = []
            
            print(f"🔍 Поиск активных аренд для телефона: '{phone}'")
            print(f"📋 Всего договоров в базе: {len(contracts)}")
            
            # Нормализуем телефон для поиска
            search_phone = self.normalize_phone(phone)
            print(f"🔍 Нормализованный телефон для поиска: '{search_phone}'")
            
            for i, contract in enumerate(contracts):
                contract_phone = str(contract.get('Телефон', ''))
                contract_status = contract.get('Статус', '')
                contract_id = contract.get('ID_договора', '') or contract.get('ID договора', '')
                
                # Нормализуем телефон из договора
                normalized_contract_phone = self.normalize_phone(contract_phone)
                
                print(f"🔍 Договор {i+1}:")
                print(f"   📱 Телефон: '{contract_phone}' -> '{normalized_contract_phone}'")
                print(f"   📄 Статус: '{contract_status}'")
                print(f"   🔢 ID договора: '{contract_id}'")
                
                if (normalized_contract_phone == search_phone and 
                    contract_status == 'активно'):
                    print(f"✅ Найден активный договор: {contract_id}")
                    active_contracts.append(contract)
            
            print(f"✅ Найдено активных договоров: {len(active_contracts)}")
            
            if not active_contracts:
                return []
            
            # Ищем ВСЕ активное оборудование для этих договоров
            rentals = self.rentals_sheet.get_all_records()
            all_active_rentals = []
            
            print(f"📦 Всего записей аренды: {len(rentals)}")
            
            for contract in active_contracts:
                contract_number = contract.get('ID_договора', '') or contract.get('ID договора', '')
                contract_rentals = []
                
                print(f"🔍 Поиск оборудования для договора: {contract_number}")
                
                for j, rental in enumerate(rentals):
                    rental_contract_num = rental.get('ID_договора', '')
                    rental_status = rental.get('Статус', '')
                    
                    print(f"   Аренда {j+1}: ID_договора='{rental_contract_num}', Статус='{rental_status}'")
                    
                    if (rental_contract_num == contract_number and 
                        rental_status == 'активно'):
                        print(f"   ✅ Найдено активное оборудование")
                        contract_rentals.append(rental)
                
                print(f"✅ Для договора {contract_number} найдено оборудования: {len(contract_rentals)}")
                
                # Добавляем информацию о договоре к каждому оборудованию
                for rental in contract_rentals:
                    rental['contract_data'] = contract
                    all_active_rentals.append(rental)
            
            print(f"🎯 Итого найдено активных аренд: {len(all_active_rentals)}")
            return all_active_rentals
            
        except Exception as e:
            print(f"❌ Ошибка поиска активных аренд: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def update_rental_status(self, contract_number: str, return_time: str = None):
        """Обновление статуса только в таблице Аренды (без договоров)"""
        try:
            if not self.rentals_sheet:
                print("❌ Лист аренд не инициализирован")
                return False
                
            if not return_time:
                return_time = datetime.now().strftime("%d.%m.%Y %H:%M")
            
            # Индексы для таблицы "Аренды"
            RENTAL_STATUS_COLUMN = 6  # Статус - 7-й столбец
            RENTAL_RETURN_TIME_COLUMN = 7  # Время_возврата - 8-й столбец
            RENTAL_CONTRACT_ID_COLUMN = 0  # ID_договора - 1-й столбец
            
            rentals_data = self.rentals_sheet.get_all_values()
            
            if len(rentals_data) < 2:
                print("❌ Таблица аренд пуста")
                return False
            
            headers = rentals_data[0]
            data_rows = rentals_data[1:]
            
            print(f"🔍 Обновление статуса аренд для договора {contract_number}")
            
            equipment_list = []
            updated_rentals = 0
            
            for i, row in enumerate(data_rows, start=2):
                if (RENTAL_CONTRACT_ID_COLUMN < len(row) and 
                    str(row[RENTAL_CONTRACT_ID_COLUMN]).strip() == str(contract_number).strip() and
                    RENTAL_STATUS_COLUMN < len(row) and
                    row[RENTAL_STATUS_COLUMN].lower() == 'активно'):
                    
                    # Сохраняем информацию об оборудовании
                    equipment_type = row[2] if 2 < len(row) else ""
                    equipment_brand = row[3] if 3 < len(row) else ""
                    equipment_size = row[4] if 4 < len(row) else ""
                    
                    equipment_list.append({
                        'type': equipment_type,
                        'brand': equipment_brand,
                        'size': equipment_size
                    })
                    
                    # Обновляем статус и время возврата
                    self.rentals_sheet.update_cell(i, RENTAL_STATUS_COLUMN + 1, 'возвращено')
                    self.rentals_sheet.update_cell(i, RENTAL_RETURN_TIME_COLUMN + 1, return_time)
                    updated_rentals += 1
                    
                    print(f"✅ Обновлена аренда строка {i}: Статус -> 'возвращено'")
            
            # Увеличиваем наличие оборудования
            if equipment_list:
                self.update_equipment_availability(equipment_list, 'return')
            
            print(f"✅ Аренды обновлены для договора {contract_number}: {updated_rentals} позиций")
            return updated_rentals > 0
            
        except Exception as e:
            print(f"❌ Ошибка обновления статуса аренд: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_inventory(self):
        """Получение списка инвентаря с исправлением дубликатов"""
        try:
            if not self.inventory_sheet:
                print("❌ Лист инвентаря не инициализирован")
                return []
                
            # Получаем все данные без автоматических заголовков
            all_data = self.inventory_sheet.get_all_values()
            
            if not all_data or len(all_data) < 2:
                print("ℹ️ Таблица инвентаря пуста или содержит только заголовки")
                return []
            
            # Вручную обрабатываем заголовки
            headers = all_data[0]
            data_rows = all_data[1:]
            
            # Убираем пустые заголовки и создаем уникальные
            clean_headers = []
            header_count = {}
            
            for i, header in enumerate(headers):
                if not header.strip():  # Если заголовок пустой
                    clean_headers.append(f"Column_{i+1}")
                else:
                    # Делаем заголовки уникальными
                    if header in header_count:
                        header_count[header] += 1
                        clean_headers.append(f"{header}_{header_count[header]}")
                    else:
                        header_count[header] = 1
                        clean_headers.append(header)
            
            print(f"📋 Заголовки инвентаря: {clean_headers}")
            
            # Создаем записи вручную
            records = []
            for row in data_rows:
                if any(cell.strip() for cell in row):  # Пропускаем полностью пустые строки
                    record = {}
                    for i, header in enumerate(clean_headers):
                        if i < len(row):
                            record[header] = row[i]
                        else:
                            record[header] = ""
                    records.append(record)
            
            print(f"✅ Загружено {len(records)} записей из инвентаря")
            return records
            
        except Exception as e:
            print(f"❌ Ошибка загрузки инвентаря: {e}")
            return []
    
    def get_prices(self):
        """Получение матрицы цен с исправлением дубликатов"""
        try:
            if not self.prices_sheet:
                print("❌ Лист цен не инициализирован")
                return []
                
            # Получаем все данные без автоматических заголовков
            all_data = self.prices_sheet.get_all_values()
            
            if not all_data or len(all_data) < 2:
                print("ℹ️ Таблица цен пуста или содержит только заголовки")
                return []
            
            # Вручную обрабатываем заголовки
            headers = all_data[0]
            data_rows = all_data[1:]
            
            # Убираем пустые заголовки и создаем уникальные
            clean_headers = []
            header_count = {}
            
            for i, header in enumerate(headers):
                if not header.strip():  # Если заголовок пустой
                    clean_headers.append(f"Column_{i+1}")
                else:
                    # Делаем заголовки уникальными
                    if header in header_count:
                        header_count[header] += 1
                        clean_headers.append(f"{header}_{header_count[header]}")
                    else:
                        header_count[header] = 1
                        clean_headers.append(header)
            
            print(f"💰 Заголовки цен: {clean_headers}")
            
            # Создаем записи вручную
            records = []
            for row in data_rows:
                if any(cell.strip() for cell in row):  # Пропускаем полностью пустые строки
                    record = {}
                    for i, header in enumerate(clean_headers):
                        if i < len(row):
                            record[header] = row[i]
                        else:
                            record[header] = ""
                    records.append(record)
            
            print(f"✅ Загружено {len(records)} ценовых правил")
            return records
            
        except Exception as e:
            print(f"❌ Ошибка загрузки цен: {e}")
            return []

    def update_equipment_availability(self, equipment_list, action='rent'):
        """Обновление наличия оборудования (rent - выдача, return - возврат)"""
        try:
            if not self.inventory_sheet:
                print("❌ Лист инвентаря не инициализирован")
                return False
            
            # Обновляем данные перед операцией
            inventory = self.inventory_sheet.get_all_records()
            updated_count = 0
            
            for equipment in equipment_list:
                # Ищем оборудование в инвентаре по параметрам
                for i, item in enumerate(inventory, start=2):
                    if self.matches_equipment(item, equipment):
                        current_availability = item.get('В наличии', '0')
                        try:
                            current_count = int(current_availability)
                        except ValueError:
                            current_count = 0
                        
                        # Обновляем количество
                        if action == 'rent':
                            new_count = max(0, current_count - 1)
                        else:  # return
                            new_count = current_count + 1
                        
                        # Обновляем ячейку
                        self.inventory_sheet.update_cell(i, self.get_column_index('В наличии'), str(new_count))
                        updated_count += 1
                        print(f"✅ Обновлено наличие: {item.get('Вид', '')} {item.get('Бренд', '')} - было {current_count}, стало {new_count}")
                        break
            
            print(f"✅ Обновлено наличие для {updated_count} позиций")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка обновления наличия: {e}")
            return False

    def matches_equipment(self, inventory_item, rental_equipment):
        """Проверяет, соответствует ли запись в инвентаре арендованному оборудованию"""
        try:
            # Сравниваем основные параметры
            type_match = inventory_item.get('Вид', '') == rental_equipment.get('type', '')
            brand_match = inventory_item.get('Бренд', '') == rental_equipment.get('brand', '')
            
            # Сравниваем размер/ростовку
            inventory_size = inventory_item.get('Ростовка') or inventory_item.get('Размер', '')
            rental_size = rental_equipment.get('size', '')
            size_match = str(inventory_size) == str(rental_size)
            
            return type_match and brand_match and size_match
            
        except Exception as e:
            print(f"❌ Ошибка сравнения оборудования: {e}")
            return False

    def get_column_index(self, column_name):
        """Получает индекс столбца по названию"""
        try:
            headers = self.inventory_sheet.row_values(1)
            return headers.index(column_name) + 1  # +1 т.к. gspread использует 1-based индексацию
        except ValueError:
            print(f"❌ Столбец '{column_name}' не найден")
            return -1

    def save_order(self, contract_data, equipment_list):
        """Сохранение заказа в таблицы Договоры и Аренды"""
        try:
            if not self.contracts_sheet or not self.rentals_sheet:
                print("❌ Листы договоров или аренд не инициализированы")
                return False
                
            # Формируем список оборудования через запятую
            equipment_names = []
            for equipment in equipment_list:
                if equipment.get('full_name'):
                    equipment_names.append(equipment['full_name'])
            
            equipment_text = ", ".join(equipment_names)
            
            # Генерируем номер акта
            act_number = self.generate_act_number()
            
            # 1. Сохраняем в таблицу "Договоры" с двумя номерами
            contract_row = [
                contract_data.get('Дата', ''),
                contract_data.get('Телефон', ''),
                contract_data.get('ФИО', ''),  # ФИО из базы клиентов
                equipment_text,  # Полный список оборудования
                contract_data.get('Срок', ''),
                contract_data.get('Сумма', ''),
                contract_data.get('Оплата', ''),
                'активно',  # Статус
                '',  # Время_возврата (пусто при создании)
                contract_data.get('ID_договора', ''),  # ID договора из базы клиентов
                act_number,  # Номер акта (автоинкремент)
            ]
            
            self.contracts_sheet.append_row(contract_row)
            print(f"✅ Договор сохранен:")
            print(f"   📄 Номер акта: {act_number}")
            print(f"   📋 ID договора: {contract_data.get('ID_договора', '')}")
            print(f"   📦 Список оборудования: {equipment_text}")
            
            # 2. Сохраняем каждое оборудование в таблицу "Аренды"
            if equipment_list:
                rental_records = []
                for equipment in equipment_list:
                    rental_record = [
                        contract_data.get('ID_договора', ''),  # ID_договора (из базы клиентов)
                        act_number,  # Номер акта для связи
                        equipment.get('type', ''),            # Тип_оборудования
                        equipment.get('brand', ''),           # Бренд
                        equipment.get('size', ''),            # Размер
                        equipment.get('original_data', {}).get('Штрихкод', ''),  # Штрихкод
                        'активно',                            # Статус
                        ''                                    # Время_возврата
                    ]
                    rental_records.append(rental_record)
                
                if rental_records:
                    self.rentals_sheet.append_rows(rental_records)
                    print(f"✅ {len(rental_records)} записей сохранено в таблицу Аренды")
            
            # 3. Уменьшаем наличие оборудования
            self.update_equipment_availability(equipment_list, 'rent')
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка сохранения заказа: {e}")
            return False
    
    def get_orders(self):
        """Получение списка заказов"""
        try:
            if not self.contracts_sheet:
                print("❌ Лист договоров не инициализирован")
                return []
                
            all_data = self.contracts_sheet.get_all_values()
            
            if len(all_data) < 2:
                return []
            
            headers = all_data[0]
            data_rows = all_data[1:]
            
            records = []
            for row in data_rows:
                if any(cell.strip() for cell in row):
                    record = {}
                    for i, header in enumerate(headers):
                        if i < len(row):
                            record[header] = row[i]
                    records.append(record)
            
            return records
            
        except Exception as e:
            print(f"❌ Ошибка загрузки заказов: {e}")
            return []
