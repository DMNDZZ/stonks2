# bot.py
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from inventory_manager import InventoryManager
import os
from config import *


class RentalBot:
    def __init__(self):
        self.inventory = InventoryManager()
        self.user_sessions = {}
        from doc_generator import DocumentGenerator
        self.doc_generator = DocumentGenerator()
    
    def get_user_session(self, user_id):
        """Безопасное получение сессии пользователя"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'step': 'main_menu',
                'selected_equipment': [],
                'client_phone': None,
                'duration': None,
                'duration_name': None,
                'payment_method': None,
                'payment_name': None
            }
        return self.user_sessions[user_id]
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start - показывает главное меню с выбором бронирования/возврата"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        print(f"🔔 Пользователь: {user_id} ({user_name})")
        
        # Сбрасываем сессию
        session = self.get_user_session(user_id)
        session.update({
            'step': 'main_menu',
            'selected_equipment': [],
            'client_phone': None,
            'duration': None,
            'duration_name': None,
            'payment_method': None,
            'payment_name': None,
            'return_selected_equipment': []
        })
        
        welcome_message = (
            f"👋 Привет, {user_name}!\n\n"
            f"🏔️ Добро пожаловать в систему аренды горнолыжного оборудования!\n\n"
            f"Выберите действие:"
        )
        
        # Сразу показываем выбор бронирования/возврата
        await self.show_main_menu(update)

    async def reset_order(self, update: Update):
        """Сброс заказа и возврат в главное меню"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        session.update({
            'step': 'main_menu',
            'selected_equipment': [],
            'client_phone': None,
            'client_name': None,
            'client_passport': None,
            'contract_number': None,  # ← Добавляем очистку ID договора
            'duration': None,
            'duration_name': None,
            'payment_method': None,
            'payment_name': None,
            'return_selected_equipment': []
        })
        
        await self.show_main_menu(update)
    
    async def show_main_menu(self, update: Update):
        """ГЛАВНОЕ меню с выбором бронирования или возврата"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        
        # Сбрасываем шаг на главное меню
        session['step'] = 'main_menu'
        
        # Сбрасываем данные заказа (но не сессию полностью)
        session.update({
            'selected_equipment': [],
            'client_phone': None,
            'duration': None,
            'duration_name': None,
            'payment_method': None,
            'payment_name': None
        })
        
        keyboard = [
            [InlineKeyboardButton("📥 Бронирование оборудования", callback_data="start_rental")],
            [InlineKeyboardButton("📤 Возврат оборудования", callback_data="start_return")],
        ]
        
        message = "🏔️ Система аренды оборудования\n\nВыберите действие:"
        
        await self.send_or_edit_message(update, message, keyboard)
        
    async def show_equipment_selection_menu(self, update: Update):
        """Меню выбора оборудования (в процессе бронирования)"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        session['step'] = 'selecting_equipment'
        
        # Получаем типы оборудования в правильном порядке
        equipment_types = self.inventory.get_equipment_types_ordered()
        
        keyboard = []
        for eq_type in equipment_types:
            # НОВЫЙ ФОРМАТ с хешами
            equip_id = self.generate_callback_id(eq_type, "eq")
            session[equip_id] = eq_type
            
            # Автоматическая иконка
            icon = self.get_equipment_icon(eq_type)
            keyboard.append([InlineKeyboardButton(f"{icon} {eq_type}", callback_data=equip_id)])
        
        # Дополнительные кнопки для процесса бронирования
        keyboard.append([InlineKeyboardButton("📷 Сканировать штрихкод", callback_data="scan_barcode")])
        keyboard.append([InlineKeyboardButton("🔢 Ввести штрихкод вручную", callback_data="enter_barcode")])
        
        # Добавляем кнопку завершения выбора оборудования, если есть выбранное
        if session.get('selected_equipment'):
            keyboard.append([InlineKeyboardButton("✅ Завершить выбор оборудования", callback_data="finish_equipment")])
        
        # Кнопки навигации для процесса бронирования
        keyboard.append([InlineKeyboardButton("◀️ Назад к сроку аренды", callback_data="back_to_duration")])
        keyboard.append([InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")])
        
        message = "📦 Выберите тип оборудования:"
        
        await self.send_or_edit_message(update, message, keyboard)

    async def show_brands_menu(self, update: Update, equipment_type: str):
        """Меню выбора брендов для конкретного типа оборудования"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        session['step'] = 'selecting_equipment'
        session['current_equipment_type'] = equipment_type
        
        brands = self.inventory.get_brands(equipment_type)
        
        if not brands:
            message = f"❌ Нет доступного оборудования типа '{equipment_type}'"
            # НОВЫЙ ФОРМАТ с хешами для возврата
            back_id = self.generate_callback_id("back_to_equipment", "nav")
            session[back_id] = "back_to_equipment_selection"
            await self.send_or_edit_message(update, message, 
                [
                    [InlineKeyboardButton("◀️ Назад", callback_data=back_id)],
                    [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
                ])
            return
        
        keyboard = []
        for brand in brands:
            # НОВЫЙ ФОРМАТ с хешами
            brand_id = self.generate_callback_id(f"{equipment_type}_{brand}", "br")
            # Сохраняем данные в сессии
            session[brand_id] = {
                'equipment_type': equipment_type,
                'brand': brand
            }
            
            keyboard.append([
                InlineKeyboardButton(f"➕ {brand}", callback_data=brand_id)
            ])
        
        # НОВЫЙ ФОРМАТ с хешами для возврата
        back_id = self.generate_callback_id("back_to_equipment", "nav")
        session[back_id] = "back_to_equipment_selection"
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=back_id)])
        keyboard.append([InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")])
        
        message = f"Выберите бренд {equipment_type}:"
        await self.send_or_edit_message(update, message, keyboard)

    async def show_sizes_menu(self, update: Update, equipment_type: str, brand: str):
        """Меню выбора размеров/ростовок"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        session['step'] = 'selecting_size'
        
        sizes = self.inventory.get_sizes(equipment_type, brand)
        
        if not sizes:
            message = f"❌ Нет доступных размеров для {brand}"
            # НОВЫЙ ФОРМАТ с хешами для возврата
            back_id = self.generate_callback_id(f"{equipment_type}_back", "nav")
            session[back_id] = {
                'action': 'back_to_equipment_menu',
                'equipment_type': equipment_type
            }
            await self.send_or_edit_message(update, message,
                [
                    [InlineKeyboardButton("◀️ Назад", callback_data=back_id)],
                    [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
                ])
            return
        
        keyboard = []
        for size in sizes:
            # НОВЫЙ ФОРМАТ с хешами
            size_id = self.generate_callback_id(f"{equipment_type}_{brand}_{size}", "sel")
            # Сохраняем все данные в сессии
            session[size_id] = {
                'equipment_type': equipment_type,
                'brand': brand,
                'size': size
            }
            
            # Определяем тип размера для отображения
            if equipment_type in ['Сноуборд', 'Горные лыжи']:
                button_text = f"📏 {size} см"
            elif equipment_type in ['Ботинки сноуборд', 'Ботинки горные лыжи']:
                button_text = f"👞 Размер {size}"
            elif equipment_type == 'Шлема':
                button_text = f"🪖 Размер {size}"
            else:
                button_text = f"➕ {size}"
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=size_id)])
        
        # НОВЫЙ ФОРМАТ с хешами для возврата
        back_id = self.generate_callback_id(f"{equipment_type}_back", "nav")
        session[back_id] = {
            'action': 'back_to_equipment_menu', 
            'equipment_type': equipment_type
        }
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=back_id)])
        keyboard.append([InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")])
        
        # Определяем текст в зависимости от типа оборудования
        if equipment_type in ['Сноуборд', 'Горные лыжи']:
            size_type = "ростовку"
        else:
            size_type = "размер"
            
        message = f"Выберите {size_type} для {brand} ({equipment_type}):"
        await self.send_or_edit_message(update, message, keyboard)

    async def ask_days_count(self, update: Update):
        """Запрос количества суток для аренды"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        session['step'] = 'waiting_days_count'
        
        message = (
            "🤖 Введите количество суток аренды:\n\n"
            "_Просто введите число, например: 3_"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
        ]
        
        await self.send_or_edit_message(update, message, keyboard)

    async def request_barcode_scan(self, update: Update):
        """Запрос сканирования штрихкода через фото"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        session['step'] = 'waiting_barcode_photo'
        
        message = (
            "📷 Сфотографируйте штрихкод оборудования\n\n"
            "Или вернитесь в меню:"
        )
        
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_equipment_selection")],
            [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
        ]
        
        await self.send_or_edit_message(update, message, keyboard)
    
    async def request_barcode_manual(self, update: Update):
        """Запрос ввода штрихкода вручную (для сканеров)"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        session['step'] = 'waiting_barcode_manual'
        
        message = (
            "🔢 Введите штрихкод оборудования:\n\n"
            "Наведите сканер на штрихкод или введите код вручную"
        )
        
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_equipment_selection")],
            [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
        ]
        
        await self.send_or_edit_message(update, message, keyboard)

    def get_user_id_from_update(self, update):
        """Получение user_id из update объекта"""
        if hasattr(update, 'callback_query') and update.callback_query:
            return update.callback_query.from_user.id
        elif hasattr(update, 'message') and update.message:
            return update.message.from_user.id
        elif hasattr(update, 'effective_user'):
            return update.effective_user.id
        else:
            print("❌ Не могу определить user_id из update")
            return 0

    async def start_return_process(self, update: Update):
        """Начало процесса возврата оборудования"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        
        session.update({
            'step': 'waiting_phone_return',
            'return_equipment': [],
            'current_contract': None
        })
        
        message = (
            "📤 **ВОЗВРАТ ОБОРУДОВАНИЯ**\n\n"
            "📱 Введите номер телефона клиента для поиска активных аренд:"
        )
        
        keyboard = [
            [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_main")],
            [InlineKeyboardButton("🔄 Сброс", callback_data="reset_order")]
        ]
        
        await self.send_or_edit_message(update, message, keyboard)

    async def process_return_phone(self, update: Update, phone: str):
        """Обработка введенного номера телефона для возврата"""
        user_id = update.message.from_user.id
        session = self.get_user_session(user_id)
        
        # Ищем активные аренды по телефону
        active_rentals = self.inventory.sheets.find_active_rentals(phone)
        
        if not active_rentals:
            message = (
                f"❌ Не найдено активных аренд для телефона: {phone}\n\n"
                f"Проверьте номер или вернитесь в меню:"
            )
            
            keyboard = [
                [InlineKeyboardButton("📱 Ввести другой номер", callback_data="start_return")],
                [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_main")]
            ]
            
            await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        # Группируем оборудование по договорам
        contracts_equipment = {}
        for rental in active_rentals:
            contract_num = rental.get('ID_договора')
            if contract_num not in contracts_equipment:
                contracts_equipment[contract_num] = {
                    'contract_data': rental.get('contract_data', {}),
                    'equipment': []
                }
            contracts_equipment[contract_num]['equipment'].append(rental)
        
        # Если несколько договоров - показываем выбор
        if len(contracts_equipment) > 1:
            await self.show_contract_selection(update, contracts_equipment, phone)
        else:
            # Если один договор - сразу показываем подтверждение возврата
            contract_num = list(contracts_equipment.keys())[0]
            await self.show_return_confirmation(update, contract_num, contracts_equipment[contract_num], phone)

    async def show_contract_selection(self, update: Update, contracts_equipment: dict, phone: str):
        """Показ выбора договора (если несколько активных)"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        session['step'] = 'selecting_contract'
        session['contracts_equipment'] = contracts_equipment
        session['return_phone'] = phone
        
        print(f"🔍 DEBUG show_contract_selection:")
        print(f"   Найдено договоров: {len(contracts_equipment)}")
        
        keyboard = []
        for contract_num, data in contracts_equipment.items():
            contract_data = data['contract_data']
            equipment_count = len(data['equipment'])
            
            # ПРАВИЛЬНО извлекаем номер акта из данных договора
            act_number = contract_data.get('Номер акта', '') 
            if not act_number:
                # Альтернативные способы найти номер акта
                for key, value in contract_data.items():
                    if 'акт' in key.lower():
                        act_number = value
                        break
            
            print(f"🔍   Договор {contract_num}: акт={act_number}, оборудование={equipment_count}")
            
            button_text = f"📄 Договор {contract_num} (акт {act_number}, {equipment_count} позиций)"
            callback_data = f"return_contract_{contract_num}"
            
            # Сохраняем оба номера в сессии
            session[callback_data] = {
                'contract_number': contract_num,
                'act_number': act_number
            }
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        keyboard.append([InlineKeyboardButton("◀️ Ввести другой номер", callback_data="start_return")])
        keyboard.append([InlineKeyboardButton("🏔️ Главное меню", callback_data="back_to_main")])
        
        message = (
            f"📱 Найдено несколько активных договоров для телефона: {phone}\n\n"
            f"Выберите договор для возврата:"
        )
        
        await self.send_or_edit_message(update, message, keyboard)

    async def show_return_confirmation(self, update: Update, contract_number: str, act_number: str, contract_data: dict, phone: str):
        """Показ подтверждения возврата с РАСЧЕТОМ СТОИМОСТИ"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        
        print(f"🔍 DEBUG show_return_confirmation:")
        print(f"   contract_number: {contract_number}")
        print(f"   act_number: {act_number}")

        session['step'] = 'confirming_return'
        session['current_contract'] = contract_number
        session['current_act_number'] = act_number  # ← Сохраняем номер акта
        session['return_phone'] = phone
        session['contract_equipment'] = contract_data['equipment']
        
        equipment_list = contract_data['equipment']
        contract_info = contract_data['contract_data']
        
        print(f"🔍 Подтверждение возврата: договор={contract_number}, акт={act_number}")
        
        # ФИКСИРУЕМ ВРЕМЯ ВОЗВРАТА И СРАЗУ СЧИТАЕМ СТОИМОСТЬ
        from datetime import datetime
        return_time = datetime.now()
        
        # Получаем данные о первоначальной аренде по НОМЕРУ АКТА
        original_rental_data = self.get_original_rental_data(act_number)
        
        if original_rental_data:
            # РАСЧЕТ СТОИМОСТИ ПРЯМО ЗДЕСЬ
            final_price, actual_period_name = self.calculate_final_price(original_rental_data, return_time)
            
            # Сохраняем для использования при подтверждении оплаты
            session['final_price'] = final_price
            session['return_time'] = return_time
            session['rental_period'] = actual_period_name
            session['original_rental_data'] = original_rental_data
            
            # Формируем список оборудования
            equipment_text = "\n".join([
                f"• {eq.get('Тип_оборудования', '')} {eq.get('Бренд', '')} {eq.get('Размер', '')}"
                for eq in equipment_list
            ])
            
            message = (
                f"📤 **ПОДТВЕРЖДЕНИЕ ВОЗВРАТА**\n\n"
                f"📄 **Договор:** №{contract_number}\n"
                f"📄 **Акт:** №{act_number}\n"
                f"📱 **Телефон:** {phone}\n"
                f"🕒 **Время выдачи:** {original_rental_data.get('issue_time').strftime('%d.%m.%Y %H:%M')}\n"
                f"🕒 **Время возврата:** {return_time.strftime('%d.%m.%Y %H:%M')}\n"
                f"⏱️ **Фактический срок:** {actual_period_name}\n"
                f"💰 **Сумма к оплате:** {final_price}₽\n\n"
                f"📦 **Оборудование для возврата:**\n"
                f"{equipment_text}\n\n"
                f"✅ **Вернуть всё оборудование и перейти к оплате?**"
            )
        else:
            # Если не удалось получить данные для расчета
            equipment_text = "\n".join([
                f"• {eq.get('Тип_оборудования', '')} {eq.get('Бренд', '')} {eq.get('Размер', '')}"
                for eq in equipment_list
            ])
            
            message = (
                f"📤 **ПОДТВЕРЖДЕНИЕ ВОЗВРАТА**\n\n"
                f"📄 **Договор:** №{contract_number}\n"
                f"📄 **Акт:** №{act_number}\n"
                f"📱 **Телефон:** {phone}\n"
                f"⏱️ **Изначальный срок:** {contract_info.get('Срок', '')}\n"
                f"💰 **Сумма:** Рассчитается при подтверждении\n\n"
                f"📦 **Оборудование для возврата:**\n"
                f"{equipment_text}\n\n"
                f"⚠️ **Стоимость будет рассчитана по фактическому времени аренды**\n\n"
                f"✅ **Вернуть всё оборудование?**"
            )
        
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить возврат", callback_data="confirm_full_return")],
            [InlineKeyboardButton("📱 Ввести другой номер", callback_data="start_return")],
            [InlineKeyboardButton("🏔️ Главное меню", callback_data="back_to_main")]
        ]
        
        await self.send_or_edit_message(update, message, keyboard)

    def get_original_rental_data(self, contract_number: str):
        """Получение данных о первоначальной аренде по номеру акта"""
        try:
            # Получаем ВСЕ данные из таблицы договоров
            contracts_data = self.inventory.sheets.contracts_sheet.get_all_values()
            
            if len(contracts_data) < 2:
                print("❌ Таблица договоров пуста")
                return None
            
            headers = contracts_data[0]
            data_rows = contracts_data[1:]
            
            # ЯВНО указываем индексы столбцов
            CONTRACT_ACT_NUMBER_COLUMN = 10  # Номер акта - 11-й столбец (индекс 10)
            CONTRACT_ID_COLUMN = 9           # ID_договора - 10-й столбец (индекс 9)
            CONTRACT_DATE_COLUMN = 0         # Дата - 1-й столбец
            CONTRACT_DURATION_COLUMN = 4     # Срок - 5-й столбец
            CONTRACT_PHONE_COLUMN = 1        # Телефон - 2-й столбец
            
            print(f"🔍 Поиск аренды по номеру акта: {contract_number}")
            print(f"🔍 Заголовки договоров: {headers}")
            
            # Ищем договор по НОМЕРУ АКТА (уникальный для каждой аренды)
            original_contract = None
            contract_row = None
            
            for i, row in enumerate(data_rows):
                if (CONTRACT_ACT_NUMBER_COLUMN < len(row) and 
                    str(row[CONTRACT_ACT_NUMBER_COLUMN]).strip() == str(contract_number).strip()):
                    
                    # Создаем словарь договора
                    original_contract = {}
                    for j, header in enumerate(headers):
                        if j < len(row):
                            original_contract[header] = row[j]
                        else:
                            original_contract[header] = ""
                    contract_row = row
                    print(f"✅ Найден договор с номером акта {contract_number} в строке {i+2}")
                    print(f"📄 Данные договора: ID={original_contract.get(headers[CONTRACT_ID_COLUMN], '')}, Срок={original_contract.get(headers[CONTRACT_DURATION_COLUMN], '')}")
                    break
            
            if not original_contract:
                print(f"❌ Договор с номером акта {contract_number} не найден в таблице договоров")
                print(f"🔍 Первые 5 номеров актов в таблице:")
                for i, row in enumerate(data_rows[:5]):
                    if CONTRACT_ACT_NUMBER_COLUMN < len(row):
                        print(f"   Строка {i+2}: '{row[CONTRACT_ACT_NUMBER_COLUMN]}'")
                return None
            
            # Получаем оборудование из таблицы "Аренды" по номеру акта
            RENTAL_ACT_NUMBER_COLUMN = 1  # Номер акта - 2-й столбец (индекс 1)
            RENTAL_TYPE_COLUMN = 2        # Тип_оборудования - 3-й столбец
            RENTAL_BRAND_COLUMN = 3       # Бренд - 4-й столбец
            RENTAL_SIZE_COLUMN = 4        # Размер - 5-й столбец
            RENTAL_STATUS_COLUMN = 6      # Статус - 7-й столбец
            
            rentals_data = self.inventory.sheets.rentals_sheet.get_all_values()
            
            if len(rentals_data) < 2:
                print("❌ Таблица аренд пуста")
                return None
            
            rental_headers = rentals_data[0]
            rental_rows = rentals_data[1:]
            
            print(f"🔍 Поиск оборудования в арендах для номера акта {contract_number}")
            
            # Фильтруем оборудование для этого номера акта со статусом "активно"
            contract_equipment = []
            for rental in rental_rows:
                if (RENTAL_ACT_NUMBER_COLUMN < len(rental) and 
                    str(rental[RENTAL_ACT_NUMBER_COLUMN]).strip() == str(contract_number).strip() and
                    RENTAL_STATUS_COLUMN < len(rental) and
                    rental[RENTAL_STATUS_COLUMN].lower() == 'активно'):
                    
                    equipment_type = rental[RENTAL_TYPE_COLUMN] if RENTAL_TYPE_COLUMN < len(rental) else ""
                    equipment_brand = rental[RENTAL_BRAND_COLUMN] if RENTAL_BRAND_COLUMN < len(rental) else ""
                    equipment_size = rental[RENTAL_SIZE_COLUMN] if RENTAL_SIZE_COLUMN < len(rental) else ""
                    
                    equipment_data = {
                        'type': equipment_type,
                        'brand': equipment_brand,
                        'size': equipment_size,
                        'full_name': f"{equipment_type} {equipment_brand} {equipment_size}".strip()
                    }
                    contract_equipment.append(equipment_data)
                    
                    print(f"🔍 Найдено оборудование: {equipment_data['full_name']}")
            
            if not contract_equipment:
                print(f"❌ Не найдено активного оборудования для номера акта {contract_number}")
                return None
            
            # Парсим дату выдачи из договора
            issue_date_str = original_contract.get(headers[CONTRACT_DATE_COLUMN], '') if CONTRACT_DATE_COLUMN < len(headers) else ''
            try:
                if ' ' in issue_date_str:
                    issue_time = datetime.strptime(issue_date_str, "%d.%m.%Y %H:%M")
                else:
                    issue_time = datetime.strptime(issue_date_str, "%d.%m.%Y")
            except Exception as date_error:
                print(f"⚠️ Ошибка парсинга даты '{issue_date_str}': {date_error}")
                issue_time = datetime.now()
            
            # Определяем тип аренды из договора
            duration_text = original_contract.get(headers[CONTRACT_DURATION_COLUMN], '') if CONTRACT_DURATION_COLUMN < len(headers) else ''
            if 'суток' in duration_text:
                duration_type = 'multiday'
                try:
                    days_count = int(''.join(filter(str.isdigit, duration_text)) or 1)
                except:
                    days_count = 1
            elif 'Сутки' in duration_text or 'сутки' in duration_text:
                duration_type = '24hours'
                days_count = 1
            else:
                duration_type = 'today'
                days_count = 1
            
            print(f"🔍 Данные аренды: {len(contract_equipment)} позиций, тип: {duration_type}, дней: {days_count}")
            
            return {
                'issue_time': issue_time,
                'duration_type': duration_type,
                'days_count': days_count,
                'selected_equipment': contract_equipment,
                'original_contract': original_contract
            }
            
        except Exception as e:
            print(f"❌ Ошибка получения данных о первоначальной аренде: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def process_full_return(self, update: Update):
        """Обработка полного возврата оборудования с расчетом оплаты"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        
        contract_number = session.get('current_contract')
        act_number = session.get('current_act_number')
        phone = session.get('return_phone')
        equipment_list = session.get('contract_equipment', [])
        
        print(f"🔍 DEBUG process_full_return:")
        print(f"   contract_number: {contract_number}")
        print(f"   act_number: {act_number}")
        print(f"   phone: {phone}")
        
        if not contract_number or not act_number:
            await self.send_or_edit_message(update, 
                "❌ Ошибка: не найден номер договора или акта",
                [[InlineKeyboardButton("📱 Начать заново", callback_data="start_return")]]
            )
            return
        
        try:
            # Фиксируем время возврата
            from datetime import datetime
            return_time = datetime.now()
            
            # Получаем данные о первоначальной аренде по НОМЕРУ АКТА
            original_rental_data = self.get_original_rental_data(act_number)
            
            if not original_rental_data:
                await self.send_or_edit_message(update,
                    "❌ Не найдены данные о первоначальной аренде",
                    [[InlineKeyboardButton("📱 Начать заново", callback_data="start_return")]]
                )
                return
            
            print(f"🔍 Данные первоначальной аренды для акта {act_number}:")
            print(f"   - Время выдачи: {original_rental_data.get('issue_time')}")
            print(f"   - Тип аренды: {original_rental_data.get('duration_type')}")
            print(f"   - Оборудование: {len(original_rental_data.get('selected_equipment', []))} позиций")
            
            # Расчет стоимости
            final_price, period_name = self.calculate_final_price(original_rental_data, return_time)
            
            # Сохраняем стоимость для выбора оплаты
            session['final_price'] = final_price
            session['return_time'] = return_time
            session['rental_period'] = period_name
            session['original_rental_data'] = original_rental_data
            
            # Показываем стоимость и запрашиваем способ оплаты
            equipment_text = "\n".join([
                f"• {eq.get('Тип_оборудования', '')} {eq.get('Бренд', '')} {eq.get('Размер', '')}"
                for eq in equipment_list
            ])
            
            message = (
                f"📊 **РАСЧЕТ СТОИМОСТИ**\n\n"
                f"📄 **Договор:** №{contract_number}\n"
                f"📄 **Акт:** №{act_number}\n"
                f"📱 **Телефон:** {phone}\n"
                f"🕒 **Время выдачи:** {original_rental_data.get('issue_time').strftime('%d.%m.%Y %H:%M')}\n"
                f"🕒 **Время возврата:** {return_time.strftime('%d.%m.%Y %H:%M')}\n"
                f"⏱️ **Период аренды:** {period_name}\n"
                f"📦 **Оборудование:**\n{equipment_text}\n\n"
                f"💰 **Итоговая стоимость:** {final_price}₽\n\n"
                f"Выберите способ оплаты:"
            )
            
            keyboard = [
                [InlineKeyboardButton("💵 Наличные", callback_data="payment_cash_return")],
                [InlineKeyboardButton("💳 Карта", callback_data="payment_card_return")],
                [InlineKeyboardButton("📱 Перевод", callback_data="payment_transfer_return")],
                [InlineKeyboardButton("◀️ Назад", callback_data="start_return")]
            ]
            
            session['step'] = 'selecting_payment_return'
            
            await self.send_or_edit_message(update, message, keyboard)
            
        except Exception as e:
            print(f"❌ Ошибка при возврате: {e}")
            import traceback
            traceback.print_exc()
            message = f"❌ Ошибка при возврате: {str(e)}"
            await self.send_or_edit_message(update, message,
                [[InlineKeyboardButton("📱 Начать заново", callback_data="start_return")]])

    async def process_payment_return_selection(self, update: Update, payment_type: str):
        """Обработка выбора способа оплаты при возврате с сохранением в таблицу"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        
        # Маппинг callback_data в читаемые названия
        payment_names = {
            'cash_return': 'Наличные',
            'card_return': 'Карта', 
            'transfer_return': 'Перевод'
        }
        
        payment_name = payment_names.get(payment_type, payment_type)
        
        # ВАЖНО: используем номер акта из сессии, а не номер договора
        act_number = session.get('current_act_number')  # ← Правильно: номер акта
        return_time = session.get('return_time')
        final_price = session.get('final_price')
        contract_number = session.get('current_contract')  # ← ID договора для информации
        
        if not act_number:
            await self.send_or_edit_message(update,
                "❌ Ошибка: не найден номер акта",
                [[InlineKeyboardButton("📱 Начать заново", callback_data="start_return")]]
            )
            return
        
        # Обновляем статус в таблицах по НОМЕРУ АКТА
        success = self.update_contract_with_payment(act_number, final_price, payment_name, return_time)
        
        if success:
            # Сохраняем информацию об оплате
            self.save_payment_info(contract_number, final_price, payment_name)
            
            message = (
                f"🎉 **ВОЗВРАТ ВЫПОЛНЕН**\n\n"
                f"📄 **Договор:** №{contract_number}\n"
                f"📄 **Акт:** №{act_number}\n"
                f"💰 **Сумма к оплате:** {final_price}₽\n"
                f"💳 **Способ оплаты:** {payment_name}\n"
                f"✅ Оплата получена, возврат завершен."
            )
        else:
            message = "❌ Ошибка при обновлении статуса возврата"
        
        # Кнопки для продолжения
        keyboard = [
            [InlineKeyboardButton("📤 Новый возврат", callback_data="start_return")],
            [InlineKeyboardButton("🏔️ Главное меню", callback_data="back_to_main")]
        ]
        
        # Очищаем сессию возврата
        session.update({
            'return_equipment': [],
            'current_contract': None,
            'current_act_number': None,
            'return_phone': None,
            'contracts_equipment': None,
            'contract_equipment': None,
            'final_price': None,
            'return_time': None,
            'rental_period': None,
            'original_rental_data': None
        })
        
        await self.send_or_edit_message(update, message, keyboard)

    def save_payment_info(self, contract_number: str, amount: float, payment_method: str):
        """Сохранение информации об оплате"""
        try:
            # Здесь можно добавить логику сохранения в таблицу оплат
            print(f"💰 Сохранение оплаты: договор {contract_number}, сумма {amount}₽, способ {payment_method}")
            # Пока просто логируем, можно добавить запись в Google Sheets
        except Exception as e:
            print(f"❌ Ошибка сохранения информации об оплате: {e}")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий кнопок"""
        query = update.callback_query
        user_id = query.from_user.id
        user_name = query.from_user.first_name
        
        callback_data = query.data
        
        print(f"🔔 CALLBACK получен: '{callback_data}' от {user_name}")
        
        await query.answer()
        
        session = self.get_user_session(user_id)
        
        try:
            if callback_data == 'start_new':
                await self.start_from_callback(update, context)
            
            elif callback_data == 'reset_order':
                await self.reset_order(update)
            
            elif callback_data.startswith('eq_'):
                # Тип оборудования из главного меню
                equipment_type = session.get(callback_data)
                if equipment_type:
                    print(f"🔔 Обрабатываем equip: {equipment_type}")
                    await self.show_brands_menu(update, equipment_type)
                else:
                    print(f"❌ Не найден тип оборудования для: {callback_data}")
                    await query.message.reply_text("❌ Ошибка данных. Используйте /start для перезапуска.")
            
            elif callback_data == 'back_to_name_input':
                print("🔔 Возврат к вводу ФИО")
                user_id = query.from_user.id
                session = self.get_user_session(user_id)
                session['step'] = 'waiting_client_name'
                
                message = (
                    f"📱 **ШАГ 1 из 5: КОНТАКТНЫЕ ДАННЫЕ**\n\n"
                    f"📱 **Телефон:** {session.get('client_phone', '')}\n\n"
                    f"👤 Введите ФИО клиента:\n\n"
                    f"_Пример: Иванов Иван Иванович_"
                )
                
                keyboard = [
                    [InlineKeyboardButton("◀️ Назад к вводу телефона", callback_data="start_rental")],
                    [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
                ]
                
                await self.send_or_edit_message(update, message, keyboard)

            elif callback_data in ['payment_cash_return', 'payment_card_return', 'payment_transfer_return']:
                payment_type = callback_data
                print(f"🔔 Обрабатываем payment при возврате: {payment_type}")
                await self.process_payment_return_selection(update, payment_type)

            elif callback_data == 'skip_mark_signed':
                await query.message.reply_text("ℹ️ Статус договора не изменен")

            elif callback_data == 'back_to_duration':
                print("🔔 Возврат к выбору типа аренды")
                await self.back_to_duration_selection(update)

            elif callback_data.startswith('br_'):
                # Выбор бренда - ИСПРАВЛЕННАЯ ЧАСТЬ
                brand_data = session.get(callback_data)
                if brand_data:
                    equipment_type = brand_data.get('equipment_type')
                    brand = brand_data.get('brand')
                    
                    if equipment_type and brand:
                        print(f"🔔 Обрабатываем brand: {equipment_type} -> {brand}")
                        await self.show_sizes_menu(update, equipment_type, brand)
                    else:
                        print(f"❌ Не найдены данные бренда для: {callback_data}")
                        await query.message.reply_text("❌ Ошибка данных. Вернитесь в главное меню.")
                else:
                    print(f"❌ Не найден бренд для: {callback_data}")
                    await query.message.reply_text("❌ Ошибка данных. Вернитесь в главное меню.")
            
            elif callback_data.startswith('return_contract_'):
                contract_data_dict = session.get(callback_data)
                contracts_equipment = session.get('contracts_equipment', {})
                phone = session.get('return_phone', '')
                
                print(f"🔍 DEBUG return_contract callback:")
                print(f"   contract_data_dict: {contract_data_dict}")
                
                if contract_data_dict:
                    contract_number = contract_data_dict['contract_number']
                    act_number = contract_data_dict['act_number']
                    
                    print(f"🔍   Выбран договор: {contract_number}, акт: {act_number}")
                    
                    if contract_number in contracts_equipment:
                        # Вызываем с правильными аргументами
                        await self.show_return_confirmation(update, contract_number, act_number, 
                                                        contracts_equipment[contract_number], phone)
                    else:
                        await query.message.reply_text("❌ Ошибка выбора договора")

            elif callback_data == 'confirm_full_return':
                print("🔔 Подтверждение полного возврата")
                await self.process_full_return(update)

            elif callback_data == 'back_to_equipment_selection':
                print("🔔 Возврат к выбору оборудования")
                await self.show_equipment_selection_menu(update)

            elif callback_data.startswith('sel_'):
                # Выбор размера
                selection_data = session.get(callback_data)
                if selection_data:
                    equipment_type = selection_data['equipment_type']
                    brand = selection_data['brand']
                    size = selection_data['size']
                    
                    print(f"🔔 Обрабатываем select: {equipment_type} {brand} {size}")
                    await self.add_equipment_to_order(update, equipment_type, brand, size)
                else:
                    print(f"❌ Не найдены данные для выбора: {callback_data}")
                    await query.message.reply_text("❌ Ошибка данных. Вернитесь к выбору оборудования.")

            elif callback_data.startswith('nav_'):
                # Навигационные кнопки - ИСПРАВЛЕННАЯ ЧАСТЬ
                nav_data = session.get(callback_data)
                if nav_data:
                    # Проверяем тип данных - может быть как строкой, так и словарем
                    if isinstance(nav_data, dict):
                        action = nav_data.get('action')
                        if action == 'back_to_equipment_selection':
                            print("🔔 Возврат к выбору оборудования")
                            await self.show_equipment_selection_menu(update)
                        elif action == 'back_to_equipment_menu':
                            equipment_type = nav_data.get('equipment_type')
                            print(f"🔔 Возврат к выбору бренда: {equipment_type}")
                            await self.show_brands_menu(update, equipment_type)
                    elif isinstance(nav_data, str):
                        # Обработка строковых навигационных команд
                        if nav_data == 'back_to_equipment_selection':
                            print("🔔 Возврат к выбору оборудования")
                            await self.show_equipment_selection_menu(update)
                        elif 'back_to_equipment_menu' in nav_data:
                            # Извлекаем тип оборудования из строки
                            equipment_type = nav_data.replace('back_to_equipment_menu_', '')
                            print(f"🔔 Возврат к выбору бренда: {equipment_type}")
                            await self.show_brands_menu(update, equipment_type)

            elif callback_data in ['duration_today', 'duration_24hours', 'duration_multiday']:
                duration_type = callback_data.replace('duration_', '')
                print(f"🔔 Обрабатываем duration: {duration_type}")
                await self.process_duration_selection(update, duration_type)

            # Обработка оплаты при возврате
            elif callback_data.startswith('payment_') and session.get('step') == 'selecting_payment_return':
                payment_type = callback_data.replace('payment_', '')
                print(f"🔔 Обрабатываем payment при возврате: {payment_type}")
                await self.process_payment_return_selection(update, payment_type)
            
            elif callback_data == 'back_to_main':
                print("🔔 Возврат в главное меню")
                await self.show_main_menu(update)
            
            elif callback_data == 'finish_equipment':
                print("🔔 Завершение выбора оборудования")
                await self.finish_equipment_selection(update)
            
            elif callback_data == 'confirm_order':
                print("🔔 Подтверждение заказа")
                await self.create_contract(update)
            
            elif callback_data == 'back_to_duration':
                print("🔔 Возврат к выбору срока аренды")
                await self.back_to_duration_selection(update)

            elif callback_data == 'back_to_payment':
                print("🔔 Возврат к выбору оплаты")
                await self.back_to_payment(update)

            elif callback_data == 'scan_barcode':
                print("🔔 Сканирование штрихкода")
                await self.request_barcode_scan(update)

            elif callback_data == 'enter_barcode':
                print("🔔 Ввод штрихкода вручную")
                await self.request_barcode_manual(update)
            
            elif callback_data == 'start_rental':
                print("🔔 Начало бронирования")
                await self.start_from_callback(update, context)
            
            elif callback_data == 'start_return':
                print("🔔 Начало возврата")
                await self.start_return_process(update)
            
            elif callback_data == 'stats':
                print("🔔 Просмотр статистики")
                await self.show_stats(update)

            elif callback_data == 'finish_return':
                print("🔔 Завершение возврата")
                await self.finish_return_process(update)

            else:
                print(f"❌ Неизвестный callback: {callback_data}")
                await query.message.reply_text("❌ Неизвестная команда. Используйте /start для начала работы.")

        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА в обработчике callback: {e}")
            print(f"❌ Callback data: {callback_data}")
            import traceback
            traceback.print_exc()
            
            try:
                await query.message.reply_text(
                    "❌ Произошла ошибка при обработке команды. "
                    "Используйте /start для перезапуска бота."
                )
            except Exception as send_error:
                print(f"❌ Не удалось отправить сообщение об ошибке: {send_error}")

    def looks_like_size(self, text: str) -> bool:
        """Проверяет, похожа ли строка на размер (число или содержит цифры)"""
        if not text:
            return False
        
        # Если это чисто число
        if text.replace('DOT', '.').replace('_', '').isdigit():
            return True
        
        # Если содержит цифры
        clean_text = text.replace('DOT', '.').replace('_', '')
        return any(char.isdigit() for char in clean_text)

    async def start_from_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запуск бронирования из callback"""
        user_id = update.callback_query.from_user.id
        user_name = update.callback_query.from_user.first_name
        
        print(f"🔔 Начало бронирования от пользователя: {user_id} ({user_name})")
        
        session = self.get_user_session(user_id)
        session.update({
            'step': 'waiting_phone_rental',  # Шаг для телефона при бронировании
            'selected_equipment': [],
            'client_phone': None,
            'client_name': None,
            'client_passport': None,
            'duration': None,
            'duration_name': None,
            'payment_method': None,
            'payment_name': None
        })
        
        # Сразу запрашиваем номер телефона для бронирования
        message = (
            f"📥 **ВЫДАЧА ОБОРУДОВАНИЯ**\n\n"
            f"📱 Введите номер телефона клиента:\n\n"
            f"_Пример: 89123456789_"
        )
        
        keyboard = [
            [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_main")],
            [InlineKeyboardButton("🔄 Сброс", callback_data="reset_order")]
        ]
        
        await self.send_or_edit_message(update, message, keyboard)
    
    async def add_equipment_to_order(self, update: Update, equipment_type: str, brand: str, size: str):
        """Добавление оборудования в заказ"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        
        if 'selected_equipment' not in session:
            session['selected_equipment'] = []
        
        # Формируем название оборудования
        if equipment_type in ['Сноуборд', 'Горные лыжи']:
            equipment_name = f"{brand} {size}см"
        elif equipment_type in ['Ботинки сноуборд', 'Ботинки горные лыжи']:
            equipment_name = f"{brand} размер {size}"
        elif equipment_type == 'Шлема':
            equipment_name = f"{brand} размер {size}"
        else:
            equipment_name = f"{brand}"
        
        # Создаем запись оборудования
        equipment = {
            'type': equipment_type,
            'brand': brand,
            'size': size,
            'name': equipment_name,
            'full_name': f"{equipment_type} {equipment_name}"
        }
        
        session['selected_equipment'].append(equipment)
        
        # Показываем что добавлено
        selected_count = len(session['selected_equipment'])
        message = (
            f"✅ Добавлено: {equipment['full_name']}\n"
            f"📦 В заказе: {selected_count} позиций\n\n"
            f"Продолжайте выбор или завершите:"
        )
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить еще оборудование", callback_data="back_to_equipment_selection")],
            [InlineKeyboardButton("📷 Сканировать штрихкод", callback_data="enter_barcode")],
            [InlineKeyboardButton("✅ Завершить выбор оборудования", callback_data="finish_equipment")],
            [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
        ]
        
        await self.send_or_edit_message(update, message, keyboard)
    
    async def finish_equipment_selection(self, update: Update):
        """Завершение выбора оборудования (без оплаты)"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        
        if not session.get('selected_equipment'):
            message = "❌ Вы не выбрали ни одного оборудования"
            await self.send_or_edit_message(update, message,
                [
                    [InlineKeyboardButton("◀️ Назад к выбору", callback_data="back_to_equipment_selection")],
                    [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
                ])
            return
        
        # Показываем выбранное оборудование и переходим к подтверждению
        equipment_list = "\n".join([f"• {eq['full_name']}" for eq in session['selected_equipment']])
        message = (
            f"📄 **ПОДТВЕРЖДЕНИЕ ВЫДАЧИ**\n\n"
            f"📱 **Телефон клиента:** {session.get('client_phone', 'Не указан')}\n"
            f"⏱️ **Тип аренды:** {session.get('duration_name', 'Не указано')}\n"
            f"🕒 **Время выдачи:** {session.get('issue_time').strftime('%d.%m.%Y %H:%M')}\n"
            f"📦 **Оборудование:**\n{equipment_list}\n\n"
            f"💰 **Оплата:** Постоплата (при возврате)\n\n"
            f"Всё верно?"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить и создать договор", callback_data="confirm_order")],
            [InlineKeyboardButton("◀️ Назад к выбору оборудования", callback_data="back_to_equipment_selection")],
            [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
        ]
        
        session['step'] = 'confirming_order'
        
        await self.send_or_edit_message(update, message, keyboard)
    
    async def process_client_phone(self, update: Update, session: dict):
        """Обработка введенного номера телефона"""
        phone = session['client_phone']
        
        # Ищем клиента в базе
        existing_client = self.inventory.sheets.find_client_by_phone(phone)
        
        if existing_client:
            # Клиент найден - используем существующие данные и ID договора из базы
            session['client_name'] = existing_client.get('ФИО', '')
            session['client_passport'] = existing_client.get('Серия и номер паспорта', '')
            session['contract_number'] = existing_client.get('ID договора', '')  # ← Берем из базы
            session['existing_client'] = True
            
            message = (
                f"📱 **ШАГ 1 из 4: КОНТАКТНЫЕ ДАННЫЕ**\n\n"
                f"✅ Клиент найден в базе:\n"
                f"📱 **Телефон:** {phone}\n"
                f"👤 **ФИО:** {session['client_name']}\n"
                f"📄 **Паспорт:** {session['client_passport']}\n"
                f"📄 **ID договора:** {session['contract_number']}\n\n"
                f"**ШАГ 2 из 4: ТИП АРЕНДЫ**\n\n"
                f"Выберите тип аренды:"
            )
            
            # ОБНОВЛЕННЫЕ КНОПКИ - только 3 варианта
            keyboard = [
                [InlineKeyboardButton("🏃 На сегодня", callback_data="duration_today")],
                [InlineKeyboardButton("🌙 Сутки", callback_data="duration_24hours")],
                [InlineKeyboardButton("📅 Несколько суток", callback_data="duration_multiday")],
                [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
            ]
            
            session['step'] = 'selecting_duration'
            
            await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            # Новый клиент - запрашиваем данные
            session['step'] = 'waiting_client_name'
            session['existing_client'] = False
            
            message = (
                f"📱 **ШАГ 1 из 4: КОНТАКТНЫЕ ДАННЫЕ**\n\n"
                f"📱 **Телефон:** {phone}\n\n"
                f"👤 Введите ФИО клиента:\n\n"
                f"_Пример: Иванов Иван Иванович_"
            )
            
            keyboard = [
                [InlineKeyboardButton("◀️ Назад к вводу телефона", callback_data="start_rental")],
                [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
            ]
            
            await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

    async def process_client_name(self, update: Update, name: str):
        """Обработка введенного ФИО клиента"""
        user_id = update.message.from_user.id
        session = self.get_user_session(user_id)
        
        session['client_name'] = name
        session['step'] = 'waiting_client_passport'
        
        message = (
            f"📱 **ШАГ 1 из 5: КОНТАКТНЫЕ ДАННЫЕ**\n\n"
            f"📱 **Телефон:** {session.get('client_phone', '')}\n"
            f"👤 **ФИО:** {name}\n\n"
            f"📄 Введите серию и номер паспорта:\n\n"
            f"_Пример: 4510 123456_"
        )
        
        keyboard = [
            [InlineKeyboardButton("◀️ Назад к вводу ФИО", callback_data="back_to_name_input")],
            [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
        ]
        
        await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

    async def process_client_passport(self, update: Update, passport: str):
        """Обработка введенного паспорта и сохранение клиента в базу"""
        user_id = update.message.from_user.id
        session = self.get_user_session(user_id)
        
        session['client_passport'] = passport
        
        # Сохраняем клиента в базу сразу после ввода паспорта
        if not session.get('existing_client', False):
            from datetime import datetime
            current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
            
            # Генерируем ID договора для нового клиента через sheets
            contract_number = self.inventory.sheets.generate_contract_number()
            session['contract_number'] = contract_number
            
            client_data = {
                'Дата': current_date,
                'ФИО': session.get('client_name', ''),
                'Паспорт': passport,
                'Телефон': session.get('client_phone', ''),
                'ID_договора': contract_number
            }
            
            success = self.inventory.sheets.save_client(client_data)
            if success:
                print(f"✅ Новый клиент сохранен в базу, ID договора: {contract_number}")
                
                # Генерируем и отправляем договор
                contract_file = self.doc_generator.generate_contract(
                    client_data, 
                    {}, 
                    self.inventory
                )
                if contract_file:
                    await self.send_document(update, contract_file, "договор")
                else:
                    await update.message.reply_text("❌ Ошибка генерации договора")
                
            else:
                print("❌ Ошибка сохранения клиента в базу")
        
        session['step'] = 'selecting_duration'
        
        message = (
            f"📱 **ШАГ 1 из 4: КОНТАКТНЫЕ ДАННЫЕ**\n\n"
            f"✅ Данные клиента сохранены:\n"
            f"📱 **Телефон:** {session.get('client_phone', '')}\n"
            f"👤 **ФИО:** {session.get('client_name', '')}\n"
            f"📄 **Паспорт:** {passport}\n"
            f"📄 **ID договора:** {session.get('contract_number', 'генерируется...')}\n\n"
            f"**ШАГ 2 из 4: ТИП АРЕНДЫ**\n\n"
            f"Выберите тип аренды:"
        )
        
        # ОБНОВЛЕННЫЕ КНОПКИ - только 3 варианта
        keyboard = [
            [InlineKeyboardButton("🏃 На сегодня", callback_data="duration_today")],
            [InlineKeyboardButton("🌙 Сутки", callback_data="duration_24hours")],
            [InlineKeyboardButton("📅 Несколько суток", callback_data="duration_multiday")],
            [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
        ]
        
        await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def send_document(self, update: Update, file_path: str, doc_type: str):
        """Отправка документа пользователю"""
        try:
            if file_path and os.path.exists(file_path):
                # Используем оригинальное имя файла
                filename = os.path.basename(file_path)
                
                with open(file_path, 'rb') as doc_file:
                    await update.effective_message.reply_document(
                        document=doc_file,
                        filename=filename,  # Используем сгенерированное имя
                        caption=f"📄 {doc_type.capitalize()} готов"
                    )
                return True
            else:
                print(f"❌ Файл {file_path} не найден")
                return False
        except Exception as e:
            print(f"❌ Ошибка отправки документа: {e}")
            return False

    async def process_duration_selection(self, update: Update, duration_type: str):
        """Обработка выбора типа аренды (фиксируем время выдачи)"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        
        from datetime import datetime
        session['issue_time'] = datetime.now()
        session['duration_type'] = duration_type  # ← Сохраняем тип аренды
        
        # Маппинг callback_data в читаемые названия
        duration_names = {
            'today': 'На сегодня',
            '24hours': 'Сутки', 
            'multiday': 'Несколько суток'
        }
        
        duration_name = duration_names.get(duration_type, duration_type)
        session['duration_name'] = duration_name
        
        # Если выбрано "Несколько суток" - запрашиваем количество
        if duration_type == 'multiday':
            session['step'] = 'waiting_days_count'
            message = (
                f"⏱️ **ШАГ 2 из 4: ТИП АРЕНДЫ**\n\n"
                f"🕒 **Время выдачи:** {session['issue_time'].strftime('%d.%m.%Y %H:%M')}\n\n"
                f"📅 Введите количество суток аренды:\n\n"
                f"_Пример: 3_"
            )
            
            keyboard = [
                [InlineKeyboardButton("◀️ Назад к выбору типа", callback_data="back_to_duration")],
                [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
            ]
            
            await self.send_or_edit_message(update, message, keyboard)
            return
        
        message = (
            f"📱 **ШАГ 1 из 4: КОНТАКТНЫЕ ДАННЫЕ**\n\n"
            f"📱 **Телефон клиента:** {session.get('client_phone', 'Не указан')}\n\n"
            f"⏱️ **ШАГ 2 из 4: ТИП АРЕНДЫ**\n\n"
            f"⏱️ **Тип аренды:** {duration_name}\n"
            f"🕒 **Время выдачи:** {session['issue_time'].strftime('%d.%m.%Y %H:%M')}\n\n"
            f"**ШАГ 3 из 4: ОБОРУДОВАНИЕ**\n\n"
            f"Теперь выберите оборудование:"
        )
        
        session['step'] = 'selecting_equipment'
        
        await self.send_or_edit_message(update, message, [])
        await self.show_equipment_selection_menu(update)
    
    async def process_payment_return_selection(self, update: Update, payment_type: str):
        """Обработка выбора способа оплаты при возврате с сохранением в таблицу"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        
        # Убираем суффикс _return для получения чистого типа оплаты
        clean_payment_type = payment_type.replace('_return', '')
        
        # Маппинг callback_data в читаемые названия
        payment_names = {
            'cash': 'Наличные',
            'card': 'Карта', 
            'transfer': 'Перевод'
        }
        
        payment_name = payment_names.get(clean_payment_type, clean_payment_type)
        
        # ВАЖНО: используем номер акта из сессии
        act_number = session.get('current_act_number')
        return_time = session.get('return_time')
        final_price = session.get('final_price')
        contract_number = session.get('current_contract')
        
        print(f"🔍 Обновление договора: акт={act_number}, сумма={final_price}, оплата={payment_name}")
        
        if not act_number:
            await self.send_or_edit_message(update,
                "❌ Ошибка: не найден номер акта",
                [[InlineKeyboardButton("📱 Начать заново", callback_data="start_return")]]
            )
            return
        
        # Обновляем статус в таблицах по НОМЕРУ АКТА
        success = self.update_contract_with_payment(act_number, final_price, payment_name, return_time)
        
        if success:
            message = (
                f"🎉 **ВОЗВРАТ ВЫПОЛНЕН**\n\n"
                f"📄 **Договор:** №{contract_number}\n"
                f"📄 **Акт:** №{act_number}\n"
                f"💰 **Сумма к оплате:** {final_price}₽\n"
                f"💳 **Способ оплаты:** {payment_name}\n"
                f"✅ Оплата получена, возврат завершен."
            )
        else:
            message = f"❌ Ошибка при обновлении статуса возврата для акта {act_number}"
        
        # Кнопки для продолжения
        keyboard = [
            [InlineKeyboardButton("📤 Новый возврат", callback_data="start_return")],
            [InlineKeyboardButton("🏔️ Главное меню", callback_data="back_to_main")]
        ]
        
        # Очищаем сессию возврата
        session.update({
            'return_equipment': [],
            'current_contract': None,
            'current_act_number': None,
            'return_phone': None,
            'contracts_equipment': None,
            'contract_equipment': None,
            'final_price': None,
            'return_time': None,
            'rental_period': None,
            'original_rental_data': None
        })
        
        await self.send_or_edit_message(update, message, keyboard)

    def update_contract_with_payment(self, act_number: str, final_price: float, payment_method: str, return_time):
        """Обновление договора по номеру акта"""
        try:
            if not self.inventory.sheets.contracts_sheet:
                print("❌ Лист договоров не инициализирован")
                return False
            
            # Правильные индексы столбцов
            CONTRACT_ACT_NUMBER_COLUMN = 10   # Номер акта (11-й столбец, индекс 10)
            CONTRACT_SUM_COLUMN = 5           # Сумма (6-й столбец)
            CONTRACT_PAYMENT_COLUMN = 6       # Оплата (7-й столбец)
            CONTRACT_STATUS_COLUMN = 7        # Статус (8-й столбец)
            CONTRACT_RETURN_TIME_COLUMN = 8   # Время возврата (9-й столбец)
            
            # Получаем все данные
            contracts_data = self.inventory.sheets.contracts_sheet.get_all_values()
            
            if len(contracts_data) < 2:
                print("❌ Таблица договоров пуста")
                return False
            
            headers = contracts_data[0]
            data_rows = contracts_data[1:]
            
            print(f"🔍 Поиск акта '{act_number}' в {len(data_rows)} строках")
            
            # Ищем договор по НОМЕРУ АКТА
            found = False
            for i, row in enumerate(data_rows, start=2):
                if CONTRACT_ACT_NUMBER_COLUMN < len(row):
                    current_act = str(row[CONTRACT_ACT_NUMBER_COLUMN]).strip()
                    search_act = str(act_number).strip()
                    
                    if current_act == search_act:
                        print(f"✅ Найден акт в строке {i}, обновляем данные...")
                        
                        # Обновляем данные договора
                        self.inventory.sheets.contracts_sheet.update_cell(i, CONTRACT_SUM_COLUMN + 1, str(final_price))
                        self.inventory.sheets.contracts_sheet.update_cell(i, CONTRACT_PAYMENT_COLUMN + 1, payment_method)
                        self.inventory.sheets.contracts_sheet.update_cell(i, CONTRACT_STATUS_COLUMN + 1, 'завершено')
                        self.inventory.sheets.contracts_sheet.update_cell(i, CONTRACT_RETURN_TIME_COLUMN + 1, return_time.strftime("%d.%m.%Y %H:%M"))
                        
                        print(f"✅ Договор обновлен: сумма={final_price}, оплата={payment_method}")
                        found = True
                        break
                else:
                    print(f"⚠️ Строка {i} слишком короткая: {len(row)} столбцов")
            
            if not found:
                print(f"❌ Акт '{act_number}' не найден в таблице")
                print(f"🔍 Доступные номера актов:")
                for i, row in enumerate(data_rows[:5]):
                    if CONTRACT_ACT_NUMBER_COLUMN < len(row):
                        print(f"   Строка {i+2}: '{row[CONTRACT_ACT_NUMBER_COLUMN]}'")
            
            return found
            
        except Exception as e:
            print(f"❌ Ошибка обновления договора: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def calculate_rental_period(self, issue_time, return_time, duration_type):
        """Расчет периода аренды и определение тарифа"""
        from datetime import datetime, timedelta
        
        time_diff = return_time - issue_time
        total_hours = time_diff.total_seconds() / 3600
        
        # Для "На сегодня" - особый расчет
        if duration_type == 'today':
            if total_hours <= 2:
                return '2 часа', total_hours
            elif total_hours <= 3:
                return '3 часа', total_hours
            else:
                return 'День', total_hours
        
        # Для "Сутки" и "Несколько суток" - считаем сутки
        elif duration_type in ['24hours', 'multiday']:
            # Округляем до целых суток в большую сторону
            days = int((total_hours + 23) // 24)  # +23 чтобы округлить вверх
            return f'{days} суток', days
        
        return 'Неизвестно', 0

    def calculate_final_price(self, session, return_time):
        """Расчет итоговой стоимости при возврате с учетом особенностей выходных"""
        from datetime import datetime, timedelta
        
        issue_time = session.get('issue_time')
        duration_type = session.get('duration_type')
        selected_equipment = session.get('selected_equipment', [])
        
        if not issue_time or not selected_equipment:
            return 0, "Неизвестно"
        
        # Определяем фактический период аренды
        time_diff = return_time - issue_time
        total_hours = time_diff.total_seconds() / 3600
        
        # Определяем тип дня (выходной/будний) для дня выдачи
        is_weekend = self.is_weekend_day(issue_time)
        day_type = "Выходные" if is_weekend else "Будни"
        
        # ОСОБАЯ ЛОГИКА ДЛЯ ВЫХОДНЫХ
        if is_weekend and duration_type == 'today':
            if total_hours <= 3:
                # В выходные минимум 3 часа
                period_name = '3 часа'
                days_count = 1
            else:
                period_name = 'День'
                days_count = 1
        else:
            # Стандартная логика для будних дней и суточной аренды
            if duration_type == 'today':
                if total_hours <= 2:
                    period_name = '2 часа'
                    days_count = 1
                elif total_hours <= 3:
                    period_name = '3 часа'
                    days_count = 1
                else:
                    period_name = 'День'
                    days_count = 1
            else:
                # Для суточной/многодневной аренды - ВСЕГДА используем "Сутки" и умножаем
                days_count = int((total_hours + 23) // 24)  # Округляем вверх до целых суток
                period_name = 'Сутки'  # ← ВСЕГДА ищем "Сутки" в таблице цен
        
        total_price = 0
        
        # Считаем комплекты и отдельное оборудование
        equipment_counts = self.count_equipment_by_type(selected_equipment)
        
        # Для многодневной аренды считаем по дням с учетом выходных/будних
        if duration_type in ['24hours', 'multiday'] and days_count > 1:
            # Расчет по каждому дню отдельно
            for day in range(days_count):
                current_day = issue_time + timedelta(days=day)
                is_day_weekend = self.is_weekend_day(current_day)
                day_type_for_day = "Выходные" if is_day_weekend else "Будни"
                
                # Для каждого дня считаем стоимость
                day_equipment_counts = self.count_equipment_by_type(selected_equipment)  # Копируем счетчик для каждого дня
                
                total_price += self.calculate_kit_prices(day_equipment_counts, period_name, day_type_for_day, 1)
                total_price += self.calculate_individual_prices(day_equipment_counts, period_name, day_type_for_day, 1)
                
                print(f"🔍 День {day+1} ({day_type_for_day}): {total_price}₽")
        else:
            # Для однодневной аренды или одной сутки
            total_price += self.calculate_kit_prices(equipment_counts, period_name, day_type, days_count)
            total_price += self.calculate_individual_prices(equipment_counts, period_name, day_type, days_count)
        
        # Формируем читаемое название периода для отображения
        if duration_type in ['24hours', 'multiday']:
            display_period_name = f"{days_count} суток"
        else:
            display_period_name = period_name
        
        print(f"🔍 ИТОГОВЫЙ РАСЧЕТ:")
        print(f"🔍 День выдачи: {day_type}, Период в таблице: {period_name}, Дней: {days_count}")
        print(f"🔍 Отображаемый период: {display_period_name}")
        print(f"🔍 Фактическое время: {total_hours:.1f} часов")
        print(f"🔍 Общая стоимость: {total_price}₽")
        
        return int(total_price), display_period_name

    def is_weekend_day(self, date):
        """Определение выходного дня с учетом особой логики"""
        weekday = date.weekday()
        hour = date.hour
        
        # Пятница: если аренда начинается в пятницу и берется на сутки или больше - выходной
        if weekday == 4:  # Пятница
            return True
        
        # Суббота: всегда выходной
        elif weekday == 5:  # Суббота
            return True
        
        # Воскресенье: 
        elif weekday == 6:  # Воскресенье
            # Если аренда на текущий день ИЛИ на сутки до 18:00 - выходной
            if hour < 18:
                return True
            # Если на сутки или больше после 18:00 - будний
            else:
                return False
        
        # Остальные дни - будни
        else:
            return False

    def calculate_kit_prices(self, equipment_counts: dict, period_name: str, day_type: str, period_multiplier: int = 1) -> float:
        """Расчет стоимости комплектов с учетом периода аренды и множителя"""
        total_kit_price = 0
        
        # КОМПЛЕКТ 1: Сноуборд + Ботинки сноуборд
        snowboard_kits = min(equipment_counts.get('Сноуборд', 0), equipment_counts.get('Ботинки сноуборд', 0))
        if snowboard_kits > 0:
            # Ищем цену комплекта для данного периода
            kit_price = self.inventory.get_price_from_table('Комплект сноуборд', period_name, day_type)
            if kit_price > 0:
                total_kit_price += kit_price * snowboard_kits * period_multiplier
                print(f"🔍 Комплект сноуборд: {snowboard_kits} шт × {kit_price}₽ × {period_multiplier} = {kit_price * snowboard_kits * period_multiplier}₽")
                
                # Вычитаем использованное оборудование
                equipment_counts['Сноуборд'] -= snowboard_kits
                equipment_counts['Ботинки сноуборд'] -= snowboard_kits
            else:
                print(f"⚠️ Цена комплекта сноуборд не найдена для периода: {period_name}")
        
        # КОМПЛЕКТ 2: Лыжи + Ботинки лыжи + Палки
        ski_kits = min(
            equipment_counts.get('Горные лыжи', 0), 
            equipment_counts.get('Ботинки горные лыжи', 0), 
            equipment_counts.get('Горнолыжные палки', 0)
        )
        if ski_kits > 0:
            # Ищем цену комплекта для данного периода
            kit_price = self.inventory.get_price_from_table('Комплект лыжи', period_name, day_type)
            if kit_price > 0:
                total_kit_price += kit_price * ski_kits * period_multiplier
                print(f"🔍 Комплект лыжи: {ski_kits} шт × {kit_price}₽ × {period_multiplier} = {kit_price * ski_kits * period_multiplier}₽")
                
                # Вычитаем использованное оборудование
                equipment_counts['Горные лыжи'] -= ski_kits
                equipment_counts['Ботинки горные лыжи'] -= ski_kits
                equipment_counts['Горнолыжные палки'] -= ski_kits
            else:
                print(f"⚠️ Цена комплекта лыжи не найдена для периода: {period_name}")
        
        print(f"🔍 Итого за комплекты: {total_kit_price}₽")
        return total_kit_price

    async def back_to_duration_selection(self, update: Update):
        """Возврат к выбору срока аренды"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        
        message = (
            f"📱 **ШАГ 1 из 4: КОНТАКТНЫЕ ДАННЫЕ**\n\n"
            f"📱 **Телефон клиента:** {session.get('client_phone', 'Не указан')}\n\n"
            f"⏱️ **ШАГ 2 из 4: ТИП АРЕНДЫ**\n\n"
            f"Выберите тип аренды:"
        )
        
        keyboard = [
            [InlineKeyboardButton("🏃 На сегодня", callback_data="duration_today")],
            [InlineKeyboardButton("🌙 Сутки", callback_data="duration_24hours")],
            [InlineKeyboardButton("📅 Несколько суток", callback_data="duration_multiday")],
            [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
        ]
        
        session['step'] = 'selecting_duration'
        
        await self.send_or_edit_message(update, message, keyboard)


    def count_equipment_by_type(self, selected_equipment: list) -> dict:
        """Автоматический подсчет ВСЕХ типов оборудования + гарантия ключей для комплектов"""
        counts = {}
        
        # Сначала считаем все автоматически
        for equipment in selected_equipment:
            eq_type = equipment.get('type')
            if eq_type:
                counts[eq_type] = counts.get(eq_type, 0) + 1
        
        # ГАРАНТИРУЕМ наличие ключей для комплектов (даже если значение 0)
        kit_equipment = [
            'Сноуборд', 'Горные лыжи', 'Ботинки сноуборд', 
            'Ботинки горные лыжи', 'Горнолыжные палки'
        ]
        
        for kit_type in kit_equipment:
            if kit_type not in counts:
                counts[kit_type] = 0
        
        print(f"🔍 Счетчик оборудования: {counts}")
        return counts

    def generate_callback_id(self, text: str, prefix: str = "id") -> str:
        """Генерирует уникальный ID для callback_data"""
        import hashlib
        
        # Создаем хеш от текста
        hash_object = hashlib.md5(text.encode())
        hash_hex = hash_object.hexdigest()[:8]
        
        return f"{prefix}_{hash_hex}"

    def safe_callback_data(self, text: str) -> str:
        """Безопасное преобразование текста для callback_data"""
        if text is None:
            return "unknown"
        
        # Простая очистка без сокращений
        safe_text = str(text).replace(' ', '_').replace('.', 'DOT')
        safe_text = ''.join(c for c in safe_text if c.isalnum() or c in ['_', '-'])
        
        return safe_text[:30]

    def get_equipment_icon(self, equipment_type: str) -> str:
        """Автоматическое определение иконки по типу оборудования"""
        if not equipment_type:
            return '➕'
        
        icon_mapping = {
            'сноуборд': '🏂',
            'лыжи': '⛷️', 
            'ботинки': '👞',
            'крепления': '🔗',
            'палки': '🎿',
            'шлем': '🪖',
            'перчатки': '🧤',
            'варежки': '🧤',
            'очки': '🥽',
            'защита': '🛡️'
        }
        
        equipment_lower = equipment_type.lower()
        for key, icon in icon_mapping.items():
            if key in equipment_lower:
                return icon
        
        return '➕'

    def calculate_individual_prices(self, equipment_counts: dict, period_name: str, day_type: str, period_multiplier: int = 1) -> float:
        """Расчет стоимости оставшегося оборудования по отдельности с учетом множителя"""
        total_individual_price = 0
        
        print(f"🔍 РАСЧЕТ ИНДИВИДУАЛЬНЫХ ЦЕН:")
        print(f"🔍 Оборудование для расчета: {equipment_counts}")
        print(f"🔍 Период: {period_name}, Тип дня: {day_type}, Множитель: {period_multiplier}")
        
        for eq_type, count in equipment_counts.items():
            if count > 0:
                price_type = self.get_equipment_price_type(eq_type)
                print(f"🔍 Оборудование: '{eq_type}' -> тип цены: '{price_type}'")
                
                price = self.inventory.get_price_from_table(price_type, period_name, day_type)
                if price > 0:
                    total_individual_price += price * count * period_multiplier
                    print(f"🔍 {eq_type}: {count} шт × {price}₽ × {period_multiplier} = {price * count * period_multiplier}₽")
                else:
                    print(f"❌ Цена 0 для: {eq_type} (тип цены: {price_type})")
        
        print(f"🔍 Итого за отдельное оборудование: {total_individual_price}₽")
        return total_individual_price

    def calculate_multi_day_price(self, session: dict) -> float:
        """Расчет цены за несколько суток с учетом дней недели"""
        total_price = 0
        days_count = session.get('days_count', 1)
        start_time = datetime.now()
        
        for day in range(days_count):
            current_day = start_time + timedelta(days=day)
            is_weekend = current_day.weekday() >= 5
            day_type = "Выходные" if is_weekend else "Будни"
            
            # Расчет для каждого оборудования в заказе
            for equipment in session['selected_equipment']:
                equipment_type = equipment['type']
                price_type = self.get_equipment_price_type(equipment_type)
                
                # РЕАЛЬНЫЙ ЗАПРОС К ТАБЛИЦЕ ЦЕН (цена за сутки)
                daily_price = self.inventory.get_price_from_table(price_type, "Сутки", day_type)
                total_price += daily_price
        
        return int(total_price)

    def get_equipment_price_type(self, equipment_type: str) -> str:
        """Определение типа цены с поддержкой комплектов"""
        # ЖЕСТКИЙ МАППИНГ только для типов, участвующих в комплектах
        price_mapping = {
            'Сноуборд': 'Сноуборд',
            'Горные лыжи': 'Горные лыжи', 
            'Ботинки сноуборд': 'Ботинки',
            'Ботинки горные лыжи': 'Ботинки',
            'Горнолыжные палки': 'Остальное',
            'Крепления': 'Остальное',
            'Шлема': 'Остальное',
            'Перчатки': 'Остальное',
            'Варежки': 'Остальное'
        }
        
        # Если тип есть в маппинге - используем его
        if equipment_type in price_mapping:
            return price_mapping[equipment_type]
        
        # Для ВСЕХ остальных типов - автоматически "Остальное"
        return 'Остальное'

    def get_duration_name(self, duration_code: str) -> str:
        """Преобразование кода срока в читаемое название для таблицы цен"""
        duration_names = {
            'today': 'День',           # Для поиска в таблице цен используем "День"
            '24hours': 'Сутки',        # Для суточной аренды
            'multiday': 'Сутки'        # Для многодневной - тоже "Сутки" (будет умножаться)
        }
        return duration_names.get(duration_code, 'Сутки')
    
    async def back_to_payment(self, update: Update):
        """Возврат к выбору способа оплаты"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        
        duration_name = session.get('duration_name', 'Не указано')
        
        message = (
            f"⏱️ Срок аренды: {duration_name}\n\n"
            f"Выберите способ оплаты:"
        )
        
        keyboard = [
            [InlineKeyboardButton("💵 Наличные", callback_data="payment_cash")],
            [InlineKeyboardButton("💳 Карта", callback_data="payment_card")],
            [InlineKeyboardButton("📱 Перевод", callback_data="payment_transfer")],
            [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
        ]
        
        session['step'] = 'selecting_payment'
        
        await self.send_or_edit_message(update, message, keyboard)
    
    async def create_contract(self, update: Update):
        """Создание договора и сохранение в Google Sheets"""
        user_id = self.get_user_id_from_update(update)
        session = self.get_user_session(user_id)
        
        # Безопасное получение данных
        client_phone = session.get('client_phone', 'Не указан')
        client_name = session.get('client_name', 'Не указан')
        client_passport = session.get('client_passport', 'Не указан')
        contract_number = session.get('contract_number', '')
        total_price = session.get('total_price', 0)
        duration_name = session.get('duration_name', 'Не указано')
        payment_name = session.get('payment_name', 'Не указано')
        selected_equipment = session.get('selected_equipment', [])
        
        try:
            # Подготавливаем данные для сохранения
            from datetime import datetime
            current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
            
            # Генерируем номер акта через sheets
            act_number = self.inventory.sheets.generate_act_number()
            print(f"📄 Сгенерирован номер акта: {act_number}")
            
            # 1. Сохраняем договор и аренду
            contract_data = {
                'Дата': current_date,
                'Телефон': client_phone,
                'ФИО': client_name,
                'Срок': duration_name,
                'Сумма': total_price,
                'Оплата': payment_name,
                'Статус': 'активно',
                'Время_возврата': '',
                'ID_договора': contract_number,
                'act_number': act_number  # ← Сохраняем номер акта
            }
            
            # Сохраняем в Google Sheets
            success = self.inventory.sheets.save_order(contract_data, selected_equipment)
            
            if success:
                # Проверяем статус подписания договора
                is_signed = self.inventory.sheets.is_contract_signed(client_phone)
                print(f"🔍 Статус подписания для {client_phone}: {is_signed}")
                
                # Подготавливаем данные для документов
                client_data_for_docs = {
                    'ID_договора': contract_number,
                    'ФИО': client_name,
                    'Паспорт': client_passport,
                    'Телефон': client_phone
                }
                
                contract_data_for_docs = {
                    'ID_договора': contract_number,
                    'ФИО': client_name,
                    'act_number': act_number,  # ← Передаем номер акта
                    'duration_type': session.get('duration_type', 'today'),
                    'days_count': session.get('days_count', 1)
                }
                
                # Генерируем и отправляем акт
                act_file = self.doc_generator.generate_act(
                    contract_data_for_docs, 
                    selected_equipment, 
                    self.inventory
                )
                
                if act_file:
                    await self.send_document(update, act_file, "акт")
                    print("✅ Акт отправлен")
                else:
                    print("❌ Ошибка генерации акта")
                
                # Если договор не подписан - отправляем договор
                if not is_signed:
                    contract_file = self.doc_generator.generate_contract(
                        client_data_for_docs, 
                        contract_data_for_docs,  # ← Передаем данные с номером акта
                        self.inventory
                    )
                    
                    if contract_file:
                        await self.send_document(update, contract_file, "договор")
                        # Автоматически отмечаем как подписанный
                        self.inventory.sheets.mark_contract_signed(client_phone)
                        print(f"✅ Договор отправлен и автоматически отмечен как подписанный для {client_phone}")
                    else:
                        print("❌ Ошибка генерации договора")
                else:
                    print(f"✅ Договор уже подписан для {client_phone}")
                
                # Восстанавливаем информационное сообщение
                equipment_list = "\n".join([f"• {eq['full_name']}" for eq in selected_equipment])
                
                # Определяем какие документы были отправлены
                documents_sent = []
                if not is_signed:
                    documents_sent.append("договор")
                documents_sent.append("акт")
                
                message = (
                    f"🎉 **Договор создан!**\n\n"
                    f"👤 **Клиент:** {client_name}\n"
                    f"📱 **Телефон:** {client_phone}\n"
                    f"📄 **Паспорт:** {client_passport}\n"
                    f"📋 **ID договора:** {contract_number}\n"
                    f"📄 **Номер акта:** {act_number}\n"  # ← ДОБАВЛЕНО
                    f"⏱️ **Срок аренды:** {duration_name}\n"
                    f"📦 **Оборудование:**\n{equipment_list}\n"
                    f"💰 **Сумма:** {total_price}₽\n"
                    f"💳 **Оплата:** {payment_name}\n\n"
                    f"✅ Отправлены документы: {', '.join(documents_sent)}\n"
                    f"✅ Данные сохранены в систему."
                )
            else:
                message = "❌ Ошибка сохранения договора в таблицу"
            
            # Кнопка возврата в главное меню
            keyboard = [
                [InlineKeyboardButton("🏔️ Главное меню", callback_data="back_to_main")],
                [InlineKeyboardButton("📥 Новое бронирование", callback_data="start_rental")]
            ]
            
            # Очищаем сессию
            session.update({
                'step': 'main_menu',
                'selected_equipment': [],
                'client_phone': None,
                'client_name': None,
                'client_passport': None,
                'contract_number': None,
                'duration': None,
                'duration_name': None,
                'payment_method': None,
                'payment_name': None,
                'existing_client': False
            })
            
            await self.send_or_edit_message(update, message, keyboard)
        
        except Exception as e:
            print(f"❌ Ошибка при создании договора: {e}")
            import traceback
            traceback.print_exc()
            message = f"❌ Ошибка при сохранении договора: {str(e)}"
            
            keyboard = [[InlineKeyboardButton("🏔️ Главное меню", callback_data="back_to_main")]]
            await self.send_or_edit_message(update, message, keyboard)

    async def process_days_count_input(self, update: Update, text: str):
        """Обработка введенного количества дней"""
        user_id = update.message.from_user.id
        session = self.get_user_session(user_id)
        
        try:
            days_count = int(text)
            if days_count < 2:
                await update.message.reply_text("❌ Минимальный срок для этого варианта - 2 суток")
                return
            
            # Сохраняем в сессию
            session['duration'] = 'multiday'
            session['days_count'] = days_count
            session['duration_name'] = f"{days_count} суток"
            
            # Переходим к выбору оборудования
            message = (
                f"📱 **ШАГ 1 из 4: КОНТАКТНЫЕ ДАННЫЕ**\n\n"
                f"📱 **Телефон клиента:** {session.get('client_phone', 'Не указан')}\n\n"
                f"⏱️ **ШАГ 2 из 4: СРОК АРЕНДЫ**\n\n"
                f"⏱️ **Срок аренды:** {days_count} суток\n\n"
                f"**ШАГ 3 из 4: ОБОРУДОВАНИЕ**\n\n"
                f"Теперь выберите оборудование:"
            )
            
            session['step'] = 'selecting_equipment'
            
            await update.message.reply_text(message)
            await self.show_equipment_selection_menu(update)
            
        except ValueError:
            await update.message.reply_text("❌ Введите корректное число суток")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        user_id = update.message.from_user.id
        text = update.message.text.strip()
        user_name = update.message.from_user.first_name
        
        session = self.get_user_session(user_id)
        
        print(f"🔔 Пользователь {user_id} ({user_name}): сообщение '{text}', шаг: {session['step']}")
        
        if session['step'] == 'waiting_phone_rental':
            # Обработка номера телефона для БРОНИРОВАНИЯ
            session['client_phone'] = text
            await self.process_client_phone(update, session)

        elif session['step'] == 'waiting_client_name':
            # Обработка ФИО клиента
            await self.process_client_name(update, text)

        elif session['step'] == 'waiting_client_passport':
            # Обработка паспорта клиента
            await self.process_client_passport(update, text)

        elif session['step'] == 'waiting_phone_return':
            # Обработка номера телефона для ВОЗВРАТА
            await self.process_return_phone(update, text)

        elif session['step'] == 'waiting_days_count':
            await self.process_days_count_input(update, text)

        elif session['step'] == 'waiting_barcode_manual':
            await self.process_barcode_input(update, text)
        
        elif session['step'] == 'waiting_barcode_photo':
            await update.message.reply_text(
                "❌ Ожидалось фото штрихкода. Используйте кнопку 'Ввести штрихкод вручную' "
                "или отправьте фото штрихкода."
            )
        else:
            await update.message.reply_text("Используйте /start для начала работы.")
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка фото со штрихкодом"""
        user_id = update.message.from_user.id
        session = self.get_user_session(user_id)
        
        if session['step'] == 'waiting_barcode_photo':
            await update.message.reply_text(
                "🔄 Обрабатываю фото...\n\n"
                "⚠️ Функция распознавания штрихкодов с фото будет добавлена позже. "
                "Пока используйте сканер или введите код вручную."
            )
        else:
            await update.message.reply_text("Сначала выберите 'Сканировать штрихкод' в меню")
    
    async def process_return_phone(self, update: Update, phone: str):
        """Обработка введенного номера телефона для возврата"""
        user_id = update.message.from_user.id
        session = self.get_user_session(user_id)
        
        # Ищем активные аренды по телефону
        active_rentals = self.inventory.sheets.find_active_rentals(phone)
        
        if not active_rentals:
            message = (
                f"❌ Не найдено активных аренд для телефона: {phone}\n\n"
                f"Проверьте номер или вернитесь в меню:"
            )
            
            keyboard = [
                [InlineKeyboardButton("📱 Ввести другой номер", callback_data="start_return")],
                [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_main")]
            ]
            
            await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        # Группируем оборудование по договорам
        contracts_equipment = {}
        for rental in active_rentals:
            contract_num = rental.get('ID_договора')
            if contract_num not in contracts_equipment:
                contracts_equipment[contract_num] = {
                    'contract_data': rental.get('contract_data', {}),
                    'equipment': []
                }
            contracts_equipment[contract_num]['equipment'].append(rental)
        
        # Если несколько договоров - показываем выбор
        if len(contracts_equipment) > 1:
            await self.show_contract_selection(update, contracts_equipment, phone)
        else:
            # Если один договор - сразу показываем подтверждение возврата
            contract_num = list(contracts_equipment.keys())[0]
            contract_data = contracts_equipment[contract_num]
            
            # Получаем номер акта из данных договора
            act_number = contract_data['contract_data'].get('Номер акта', '')
            if not act_number:
                # Пробуем найти номер акта в заголовках
                headers = list(contract_data['contract_data'].keys())
                for header in headers:
                    if 'акт' in header.lower():
                        act_number = contract_data['contract_data'].get(header, '')
                        break
            
            if not act_number:
                print(f"❌ Не найден номер акта для договора {contract_num}")
                await update.message.reply_text(
                    f"❌ Ошибка: не найден номер акта для договора {contract_num}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📱 Ввести другой номер", callback_data="start_return")]
                    ])
                )
                return
            
            # Вызываем с правильными аргументами
            await self.show_return_confirmation(update, contract_num, act_number, contract_data, phone)

    async def process_barcode_input(self, update: Update, barcode_text: str):
        """Обработка введенного штрихкода"""
        equipment = self.inventory.find_equipment_by_barcode(barcode_text)
        
        if equipment:
            await self.add_equipment_from_barcode(update, equipment)
        else:
            await update.message.reply_text(
                f"❌ Оборудование с кодом '{barcode_text}' не найдено\n\n"
                "Проверьте код или выберите оборудование из списка в меню"
            )
    
    async def add_equipment_from_barcode(self, update: Update, equipment):
        """Добавление оборудования из штрихкода с проверкой наличия"""
        user_id = update.message.from_user.id
        session = self.get_user_session(user_id)
        
        # Проверяем наличие оборудования
        if not self.inventory.is_available(equipment):
            await update.message.reply_text(
                f"❌ Оборудование {equipment.get('Бренд', '')} недоступно для аренды\n\n"
                f"Возможно, оно уже арендовано другим клиентом."
            )
            return
        
        if 'selected_equipment' not in session:
            session['selected_equipment'] = []
        
        # Проверяем, не добавлено ли уже это оборудование
        existing_barcodes = [eq.get('original_data', {}).get('Штрихкод') for eq in session['selected_equipment'] if isinstance(eq, dict) and eq.get('original_data')]
        if equipment.get('Штрихкод') in existing_barcodes:
            await update.message.reply_text(
                f"❌ {equipment['Бренд']} уже добавлен в заказ"
            )
            return
        
        # Формируем запись для заказа
        equipment_type = equipment.get('Вид', '')
        brand = equipment.get('Бренд', '')
        size = equipment.get('Ростовка') or equipment.get('Размер', '')
        
        if equipment_type in ['Сноуборд', 'Горные лыжи']:
            equipment_name = f"{brand} {size}см"
        elif equipment_type in ['Ботинки сноуборд', 'Ботинки горные лыжи']:
            equipment_name = f"{brand} размер {size}"
        elif equipment_type == 'Шлема':
            equipment_name = f"{brand} размер {size}"
        else:
            equipment_name = f"{brand}"
        
        order_equipment = {
            'type': equipment_type,
            'brand': brand,
            'size': size,
            'name': equipment_name,
            'full_name': f"{equipment_type} {equipment_name}",
            'original_data': equipment
        }
        
        session['selected_equipment'].append(order_equipment)
        
        # Показываем что добавлено и предлагаем продолжить
        selected_count = len(session['selected_equipment'])
        message = (
            f"✅ Добавлено: {order_equipment['full_name']}\n"
            f"📦 В заказе: {selected_count} позиций\n\n"
            f"Продолжайте сканирование или вернитесь в меню:"
        )
        
        keyboard = [
            [InlineKeyboardButton("📷 Сканировать еще", callback_data="enter_barcode")],
            [InlineKeyboardButton("📋 Перейти к выбору из списка", callback_data="back_to_equipment_selection")],
            [InlineKeyboardButton("✅ Завершить выбор оборудования", callback_data="finish_equipment")],
            [InlineKeyboardButton("🔄 Сброс заказа", callback_data="reset_order")]
        ]
        
        await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def send_or_edit_message(self, update, text, keyboard):
        """Универсальная отправка/редактирование сообщения"""
        try:
            if hasattr(update, 'callback_query') and update.callback_query:
                # Это callback от кнопки - редактируем существующее сообщение
                query = update.callback_query
                await query.edit_message_text(
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            elif hasattr(update, 'message') and update.message:
                # Это обычное сообщение - отправляем новое
                await update.message.reply_text(
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            elif hasattr(update, 'effective_message') and update.effective_message:
                # Альтернативный способ получения сообщения
                await update.effective_message.reply_text(
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                print("❌ Неизвестный тип update для отправки сообщения")
                # Пытаемся получить chat_id любым способом
                chat_id = None
                if hasattr(update, 'callback_query') and update.callback_query:
                    chat_id = update.callback_query.message.chat_id
                elif hasattr(update, 'message') and update.message:
                    chat_id = update.message.chat_id
                elif hasattr(update, 'effective_chat'):
                    chat_id = update.effective_chat.id
                
                if chat_id:
                    # Используем context для отправки сообщения
                    if hasattr(update, '_context') and update._context:
                        await update._context.bot.send_message(
                            chat_id=chat_id,
                            text=text,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    else:
                        print("❌ Не могу отправить сообщение - нет контекста")
        except Exception as e:
            print(f"❌ Ошибка отправки сообщения: {e}")
            # Резервный вариант - просто выводим текст
            try:
                if hasattr(update, 'message') and update.message:
                    await update.message.reply_text(text)
            except Exception as fallback_error:
                print(f"❌ Резервная отправка тоже не удалась: {fallback_error}")

    async def show_stats(self, update: Update):
        """Показ статистики (заглушка)"""
        message = "📊 Статистика будет доступна в следующем обновлении"
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
        ]
        await self.send_or_edit_message(update, message, keyboard)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    print(f"❌ Ошибка в боте: {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Пожалуйста, попробуйте снова или используйте /start"
            )
    except Exception as e:
        print(f"❌ Ошибка в обработчике ошибок: {e}")

def main():
    """Запуск бота с обработкой ошибок"""
    try:
        # Проверяем наличие токена
        if not BOT_TOKEN:
            print("❌ ОШИБКА: BOT_TOKEN не найден в config.py")
            return
        
        request = HTTPXRequest(proxy=BOT_PROXY_URL)
        get_updates_request = HTTPXRequest(proxy=BOT_PROXY_URL)

        async def get_bot_link(application):
            bot_info = await application.bot.get_me()
            print(f"🤖 Бот url: https://t.me/{bot_info.username}")

        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .request(request)
            .get_updates_request(get_updates_request)
            .post_init(get_bot_link)
            .build()
        )
        
        bot = RentalBot()
        
        # Регистрация обработчиков
        application.add_handler(CommandHandler("start", bot.start))
        application.add_handler(CallbackQueryHandler(bot.handle_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
        application.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
        
        # Обработчик ошибок
        application.add_error_handler(error_handler)
        
        print("🤖 Бот запущен...")
        print("📝 Бот готов принимать команды от всех пользователей")
        application.run_polling()
    
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАПУСКЕ: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
