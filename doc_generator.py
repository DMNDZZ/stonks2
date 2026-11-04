# doc_generator.py
from docx import Document
from datetime import datetime
import os

class DocumentGenerator:
    def __init__(self):
        self.templates_path = "templates/"
        self.output_path = "documents/"
        
        # Создаем папки если их нет
        os.makedirs(self.templates_path, exist_ok=True)
        os.makedirs(f"{self.output_path}/contracts", exist_ok=True)
        os.makedirs(f"{self.output_path}/acts", exist_ok=True)
    
    def generate_initials(self, full_name: str) -> str:
        """Генерация инициалов в формате 'Фамилия И.О.'"""
        try:
            if not full_name or not full_name.strip():
                return ""
            
            # Разбиваем ФИО на части и убираем лишние пробелы
            parts = [part.strip() for part in full_name.strip().split() if part.strip()]
            
            if len(parts) == 0:
                return ""
            
            # Если только одна часть - возвращаем как есть
            if len(parts) == 1:
                return parts[0]
            
            # Форматируем: Фамилия И.О.
            # Первая часть - фамилия (оставляем полностью)
            surname = parts[0]
            
            # Остальные части - имя и отчество (сокращаем до инициалов)
            initials = []
            for part in parts[1:]:
                if part:  # Проверяем что часть не пустая
                    initials.append(part[0].upper() + '.')
            
            # Объединяем: Фамилия + инициалы через пробел
            result = f"{surname} {' '.join(initials)}"
            
            return result.strip()
            
        except Exception as e:
            print(f"❌ Ошибка генерации инициалов: {e}")
            return full_name  # Фолбэк на полное имя

    def generate_contract(self, client_data, contract_data, inventory_manager):
        """Генерация договора для нового клиента"""
        try:
            template_path = f"{self.templates_path}dogovor_template.docx"
            
            if not os.path.exists(template_path):
                print(f"❌ Файл шаблона не найден: {template_path}")
                return None
                
            print(f"🔍 Загружаем шаблон: {template_path}")
            
            doc = Document(template_path)
            print("✅ Шаблон загружен успешно")
            
            registration_date = datetime.now().strftime("%d.%m.%Y")
            
            # Генерируем инициалы
            client_name = client_data.get('ФИО', '')
            client_initials = self.generate_initials(client_name)
            
            # Расчет дедлайна возврата
            issue_time = datetime.now()
            duration_type = contract_data.get('duration_type', 'today')
            days_count = contract_data.get('days_count', 1)
            return_deadline = self.calculate_return_deadline(issue_time, duration_type, days_count)
            
            # Заменяем поля в документе
            self.replace_placeholder(doc, "{{contract_number}}", client_data.get('ID_договора', ''))
            self.replace_placeholder(doc, "{{client_name}}", client_name)
            self.replace_placeholder(doc, "{{client_initials}}", client_initials)  # ← НОВОЕ ПОЛЕ
            self.replace_placeholder(doc, "{{registration_date}}", registration_date)
            self.replace_placeholder(doc, "{{client_passport}}", client_data.get('Паспорт', ''))
            self.replace_placeholder(doc, "{{client_phone}}", client_data.get('Телефон', ''))
            self.replace_placeholder(doc, "{{return_deadline}}", return_deadline)
            
            # Сохраняем файл
            contract_number = client_data.get('ID_договора', '')
            filename = f"договор_{contract_number}.docx"
            filepath = f"{self.output_path}contracts/{filename}"
            doc.save(filepath)
            
            print(f"✅ Договор сохранен: {filename}")
            print(f"📝 Инициалы клиента: {client_initials}")
            return filepath
            
        except Exception as e:
            print(f"❌ Ошибка генерации договора: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def calculate_return_deadline(self, issue_date, duration_type, days_count=1):
        """Расчет дедлайна возврата оборудования"""
        from datetime import datetime, timedelta
        
        if duration_type == 'today':
            # На сегодня - до 21:00 того же дня
            return_date = issue_date.replace(hour=20, minute=45, second=0, microsecond=0)
            return return_date.strftime("%d.%m.%Y %H:%M")
        
        elif duration_type == '24hours':
            # Сутки - issue_date + 1 день до 21:00
            return_date = issue_date + timedelta(days=1)
            return_date = return_date.replace(hour=20, minute=45, second=0, microsecond=0)
            return return_date.strftime("%d.%m.%Y %H:%M")
        
        elif duration_type == 'multiday':
            # Несколько суток - issue_date + days_count до 21:00
            return_date = issue_date + timedelta(days=days_count)
            return_date = return_date.replace(hour=20, minute=45, second=0, microsecond=0)
            return return_date.strftime("%d.%m.%Y %H:%M")
        
        return "не указано"

    def generate_act(self, contract_data, equipment_list, inventory_manager):
        """Генерация акта выдачи оборудования"""
        try:
            template_path = f"{self.templates_path}akt_template.docx"
            
            if not os.path.exists(template_path):
                print(f"❌ Файл шаблона не найден: {template_path}")
                return None
                
            print(f"🔍 Загружаем шаблон: {template_path}")
            doc = Document(template_path)
            print("✅ Шаблон акта загружен успешно")
            
            issue_date = datetime.now().strftime("%d.%m.%Y")
            issue_datetime = datetime.now().strftime("%d.%m.%Y %H:%M")
            
            # Генерируем инициалы
            client_name = contract_data.get('ФИО', '')
            client_initials = self.generate_initials(client_name)

            # Получаем номер акта из данных контракта
            act_number = contract_data.get('act_number', '')
            
            # Получаем себестоимость оборудования
            equipment_with_cost = []
            total_cost = 0

            # Расчет дедлайна возврата
            issue_time = datetime.now()
            duration_type = contract_data.get('duration_type', 'today')
            days_count = contract_data.get('days_count', 1)
            return_deadline = self.calculate_return_deadline(issue_time, duration_type, days_count)
            
            for i, equipment in enumerate(equipment_list, 1):
                cost = self.get_equipment_cost(equipment, inventory_manager)
                equipment_with_cost.append({
                    'number': i,
                    'name': equipment.get('full_name', ''),
                    'cost': cost
                })
                total_cost += cost
            
            # Заменяем основные поля
            self.replace_placeholder(doc, "{{contract_number}}", contract_data.get('ID_договора', ''))
            self.replace_placeholder(doc, "{{act_number}}", act_number)
            self.replace_placeholder(doc, "{{issue_date}}", issue_date)
            self.replace_placeholder(doc, "{{issue_datetime}}", issue_datetime)
            self.replace_placeholder(doc, "{{return_deadline}}", return_deadline)
            self.replace_placeholder(doc, "{{client_name}}", client_name)
            self.replace_placeholder(doc, "{{client_initials}}", client_initials)  # ← НОВОЕ ПОЛЕ
            self.replace_placeholder(doc, "{{total_cost}}", str(total_cost))
            
            # Заполняем таблицу с оборудованием
            self.fill_equipment_table(doc, equipment_with_cost)
            
            # Сохраняем файл
            safe_client_name = client_name.replace(' ', '_')
            current_date = datetime.now().strftime("%d.%m.%Y")
            filename = f"акт_{safe_client_name}_{current_date}.docx"
            filepath = f"{self.output_path}acts/{filename}"
            doc.save(filepath)
            
            print(f"✅ Акт сохранен: {filename}")
            print(f"📝 Инициалы клиента: {client_initials}")
            return filepath
            
        except Exception as e:
            print(f"❌ Ошибка генерации акта: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_equipment_cost(self, equipment, inventory_manager):
        """Получение себестоимости оборудования из инвентаря"""
        try:
            # Используем свойство inventory вместо метода get_inventory()
            inventory = inventory_manager.inventory
            
            print(f"🔍 Поиск себестоимости для: {equipment.get('type', '')} {equipment.get('brand', '')} {equipment.get('size', '')}")
            print(f"🔍 Всего позиций в инвентаре: {len(inventory)}")
            
            for i, item in enumerate(inventory):
                # Сравниваем оборудование по отдельным параметрам
                type_match = item.get('Вид', '') == equipment.get('type', '')
                brand_match = item.get('Бренд', '') == equipment.get('brand', '')
                
                # Сравниваем размер/ростовку (приводим к строке и убираем лишние пробелы)
                inventory_size = str(item.get('Ростовка') or item.get('Размер', '') or '').strip()
                equipment_size = str(equipment.get('size', '')).strip()
                size_match = inventory_size == equipment_size
                
                if type_match and brand_match and size_match:
                    # Ищем себестоимость в разных возможных столбцах
                    cost = (item.get('Себестоимость') or 
                        item.get('Стоимость оборудования') or 
                        item.get('Стоимость') or 
                        item.get('Цена') or
                        item.get('Цена себестоимость') or
                        '0')
                    
                    print(f"✅ Найдено совпадение: {item.get('Вид', '')} {item.get('Бренд', '')} {inventory_size}")
                    print(f"💰 Себестоимость: '{cost}'")
                    
                    # Преобразуем в число
                    try:
                        clean_cost = str(cost).replace(' ', '').replace('₽', '').replace('руб', '').replace(',', '.').split('.')[0]
                        result = int(clean_cost) if clean_cost.isdigit() else 0
                        print(f"🔢 Преобразованная себестоимость: {result}")
                        return result
                    except Exception as conv_error:
                        print(f"❌ Ошибка преобразования себестоимости '{cost}': {conv_error}")
                        return 0
                
                # Отладочная информация для первых нескольких позиций
                if i < 3:  # Покажем первые 3 позиции для отладки
                    print(f"🔍 Позиция {i+1}: '{item.get('Вид', '')}' vs '{equipment.get('type', '')}' | "
                        f"'{item.get('Бренд', '')}' vs '{equipment.get('brand', '')}' | "
                        f"'{inventory_size}' vs '{equipment_size}'")
            
            print(f"❌ Оборудование не найдено в инвентаре: {equipment.get('type', '')} {equipment.get('brand', '')} {equipment.get('size', '')}")
            print(f"🔍 Просмотренные позиции инвентаря:")
            for i, item in enumerate(inventory[:5]):  # Покажем первые 5 для отладки
                cost_debug = item.get('Себестоимость') or item.get('Стоимость оборудования') or 'не найдено'
                print(f"   {i+1}. {item.get('Вид', '')} | {item.get('Бренд', '')} | {item.get('Ростовка', '')} | Себестоимость: {cost_debug}")
                
            return 0
                
        except Exception as e:
            print(f"❌ Ошибка получения себестоимости: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def fill_equipment_table(self, doc, equipment_with_cost):
        """Заполнение таблицы с оборудованием в акте"""
        try:
            if not doc.tables:
                print("❌ В документе нет таблиц")
                return
            
            table = doc.tables[0]
            print(f"🔍 Таблица найдена, строк: {len(table.rows)}, столбцов: {len(table.rows[0].cells) if table.rows else 0}")
            
            # Очищаем все строки кроме заголовка
            while len(table.rows) > 1:
                tbl = table._tbl
                tbl.remove(table.rows[1]._tr)
            
            print(f"🔍 Очищена таблица, осталось строк: {len(table.rows)}")
            
            # Добавляем строки для каждого оборудования
            for equipment in equipment_with_cost:
                row = table.add_row()
                if len(row.cells) >= 1:
                    row.cells[0].text = str(equipment['number'])
                if len(row.cells) >= 2:
                    row.cells[1].text = equipment['name']
                if len(row.cells) >= 3:
                    row.cells[2].text = str(equipment['cost'])
                
                print(f"✅ Добавлена строка: №{equipment['number']} | {equipment['name']} | {equipment['cost']} руб.")
            
            print(f"✅ Итого строк в таблице: {len(table.rows)}")
            
        except Exception as e:
            print(f"❌ Ошибка заполнения таблицы: {e}")
            import traceback
            traceback.print_exc()
    
    def replace_placeholder(self, doc, placeholder, value):
        """Замена плейсхолдера в документе"""
        try:
            for paragraph in doc.paragraphs:
                if placeholder in paragraph.text:
                    paragraph.text = paragraph.text.replace(placeholder, str(value))
            
            # Также проверяем таблицы
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if placeholder in cell.text:
                            cell.text = cell.text.replace(placeholder, str(value))
                            
        except Exception as e:
            print(f"❌ Ошибка замены плейсхолдера {placeholder}: {e}")