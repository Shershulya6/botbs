import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
import math
import matplotlib.pyplot as plt
import io
import numpy as np
import seaborn as sns
sns.set_style("whitegrid")  # Сетка в стиле seaborn
plt.style.use('seaborn-v0_8-pastel')  # Приятные пастельные цвета

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
INITIAL, PRINCIPAL, MONTHLY, RATE, YEARS, WAIT_FOR_RESTART = range(6)

# Функция для создания графика
def create_plot(principal, monthly, rate, years):
    monthly_rate = rate / 100 / 12
    months = years * 12
    x = []
    y = []
    
    current = principal
    for month in range(1, months + 1):
        current = current * (1 + monthly_rate) + monthly
        if month % 12 == 0:
            x.append(month // 12)
            y.append(current)
    
    plt.figure(figsize=(10, 6))
    plt.plot(x, y, 'b-', marker='o')
    plt.title('Рост инвестиций по годам')
    plt.xlabel('Годы')
    plt.ylabel('Сумма, руб')
    plt.grid(True)
    
    # Форматирование оси Y
    ax = plt.gca()
    ax.get_yaxis().set_major_formatter(
        plt.FuncFormatter(lambda x, p: format(int(x), ',').replace(',', ' '))
    )
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Расчет отменен. Нажмите /start чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    user = update.effective_user
    user_name = user.first_name  # Имя пользователя

    reply_keyboard = [['Рассчитать сложный процент']]
    await update.message.reply_text(
        f"Привет, {user_name}! 👋\n\n"
        "Я бот для расчета сложного процента.\n\n"
        "Я могу рассчитать:\n"
        "- Итоговую сумму инвестиций\n"
        "- Ежемесячный доход\n"
        "- Визуализацию роста капитала\n\n"
        "Нажмите кнопку ниже чтобы начать расчет:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return INITIAL

async def initial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Введите первоначальную сумму (например, 100000):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return PRINCIPAL

async def principal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        principal = float(update.message.text.replace(' ', '').replace(',', '.'))
        if principal < 0:
            await update.message.reply_text("Сумма должна быть положительной. Попробуйте еще раз:")
            return PRINCIPAL
        context.user_data['principal'] = principal
        await update.message.reply_text("Введите сумму ежемесячного пополнения (например, 10000):")
        return MONTHLY
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число. Попробуйте еще раз:")
        return PRINCIPAL

async def monthly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        monthly = float(update.message.text.replace(' ', '').replace(',', '.'))
        if monthly < 0:
            await update.message.reply_text("Сумма должна быть положительной. Попробуйте еще раз:")
            return MONTHLY
        context.user_data['monthly'] = monthly
        await update.message.reply_text("Введите годовую процентную ставку (например, 10 для 10%):")
        return RATE
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число. Попробуйте еще раз:")
        return MONTHLY

async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        rate = float(update.message.text.replace(' ', '').replace(',', '.'))
        if rate < 0:
            await update.message.reply_text("Ставка должна быть положительной. Попробуйте еще раз:")
            return RATE
        context.user_data['rate'] = rate
        await update.message.reply_text("Введите срок инвестирования в годах (например, 5):")
        return YEARS
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число. Попробуйте еще раз:")
        return RATE

async def years(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        # Получаем и очищаем ввод пользователя
        user_input = update.message.text.strip().replace(' ', '').replace(',', '.')
        if not user_input.replace('.', '').isdigit():
            await update.message.reply_text("Пожалуйста, введите число. Попробуйте еще раз:")
            return YEARS
            
        years = float(user_input)
        if years <= 0:
            await update.message.reply_text("Срок должен быть больше нуля. Попробуйте еще раз:")
            return YEARS

        # Получаем сохраненные данные
        principal = context.user_data.get('principal')
        monthly = context.user_data.get('monthly')
        rate = context.user_data.get('rate')
        
        if None in (principal, monthly, rate):
            await update.message.reply_text("Ошибка данных. Начните заново /start")
            return ConversationHandler.END

        # Расчетные параметры
        monthly_rate = rate / 100 / 12
        months = int(years * 12)
        
        # Пошаговый расчет с ежемесячным пополнением
        monthly_data = []
        total = principal
        for month in range(1, months + 1):
            total = total * (1 + monthly_rate) + monthly
            monthly_data.append(total)
        
        total_invested = principal + monthly * months
        income = total - total_invested
        monthly_income = total * monthly_rate

        # Создаем графики
        try:
            plot_buf_yearly = create_yearly_plot(principal, monthly, rate, years)
            plot_buf_monthly = create_monthly_plot(monthly_data, years)
            plot_buf_income = create_monthly_income_plot(monthly_data, monthly, rate, years)
        except Exception as e:
            logger.error(f"Ошибка при создании графиков: {e}")
            plot_buf_yearly = None
            plot_buf_monthly = None
            plot_buf_income = None

        # Форматируем числа
        def format_num(num):
            return f"{num:,.2f}".replace(",", " ").replace(".", ",")
        
        # Формируем сообщение
        result_msg = (
            f"📊 Результаты расчета:\n\n"
            f"• Начальная сумма: {format_num(principal)} руб\n"
            f"• Ежемесячное пополнение: {format_num(monthly)} руб\n"
            f"• Годовая ставка: {rate}%\n"
            f"• Срок: {years} лет ({months} месяцев)\n\n"
            f"💵 Итоговая сумма: {format_num(total)} руб\n"
            f"💰 Всего вложено: {format_num(total_invested)} руб\n"
            f"📈 Общий доход: {format_num(income)} руб\n"
            f"📈 Доходность: {format_num(income / total_invested * 100)}%\n\n"
            f"💸 Ежемесячный доход на конец срока: {format_num(monthly_income)} руб"
        )

        # Отправляем результат
        if plot_buf_yearly:
            await update.message.reply_photo(photo=plot_buf_yearly, caption="Рост капитала по годам")
        if plot_buf_monthly:
            await update.message.reply_photo(photo=plot_buf_monthly, caption="Рост капитала по месяцам")
        if plot_buf_income:
            await update.message.reply_photo(photo=plot_buf_income, caption="Ежемесячный доход от капитализации")
        
        await update.message.reply_text(result_msg)

        # Предлагаем новый расчет
        reply_markup = ReplyKeyboardMarkup(
            [["🔄 Новый расчет"]], resize_keyboard=True
        )
        await update.message.reply_text(
            "Нажмите кнопку для нового расчета:",
            reply_markup=reply_markup
        )

        return WAIT_FOR_RESTART

    except ValueError:
        await update.message.reply_text("Некорректный ввод. Введите число:")
        return YEARS
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        await update.message.reply_text(
            "Произошла непредвиденная ошибка. Начните заново /start",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

def create_yearly_plot(principal, monthly, rate, years):
    """Создает график роста капитала по годам"""
    monthly_rate = rate / 100 / 12
    months = int(years * 12)  # Явное преобразование в int
    x = []
    y = []
    
    current = principal
    for month in range(1, months + 1):
        current = current * (1 + monthly_rate) + monthly
        if month % 12 == 0:
            x.append(month // 12)
            y.append(current)
    
    plt.figure(figsize=(10, 5))
    plt.plot(x, y, 'b-', marker='o')
    plt.title('Рост капитала по годам')
    plt.xlabel('Годы')
    plt.ylabel('Сумма, руб')
    plt.grid(True)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

def create_monthly_plot(monthly_data, years):
    """Создает график роста капитала по месяцам"""
    plt.figure(figsize=(12, 6))
    
    # Преобразуем years в int для расчета шага
    years_int = int(years)
    step = 6 if years_int >= 3 else 3 if years_int >= 1 else 1
    
    x = list(range(1, len(monthly_data)+1))
    plt.plot(x, monthly_data, 'g-', linewidth=1.5)
    plt.title('Рост капитала по месяцам')
    plt.xlabel('Месяцы')
    plt.ylabel('Сумма, руб')
    plt.grid(True)
    plt.xticks(x[::step])
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

# ===== ДОБАВЛЯЕМ НОВУЮ ФУНКЦИЮ ДЛЯ ГРАФИКА ДОХОДА =====
def create_monthly_income_plot(monthly_data, monthly_contrib, rate, years):
    """Создает график ежемесячного дохода"""
    monthly_rate = rate / 100 / 12
    x = list(range(1, len(monthly_data)+1))
    income_per_month = []
    
    prev_value = monthly_contrib  # начальная сумма + первое пополнение
    for current_value in monthly_data:
        income = current_value - prev_value - monthly_contrib
        income_per_month.append(income)
        prev_value = current_value
    
    plt.figure(figsize=(12, 6))
    plt.plot(x, income_per_month, 'r-', linewidth=1.5)
    plt.title('Ежемесячный доход от капитализации')
    plt.xlabel('Месяцы')
    plt.ylabel('Доход, руб')
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Уменьшаем количество подписей на оси X
    step = 6 if years >= 3 else 3 if years >= 1 else 1
    plt.xticks(x[::step])
    
    # Форматируем числа с пробелами
    ax = plt.gca()
    ax.get_yaxis().set_major_formatter(
        plt.FuncFormatter(lambda x, p: format(int(x), ',').replace(',', ' '))
    )
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=80, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Начинаем новый расчет
    await initial(update, context)
    return PRINCIPAL

def main() -> None:
    # Создаем приложение
    application = Application.builder().token("7827428493:AAHlNg4GurlW9q1uuvYyiXMH9ZPYcIsOfXs").build()
    
    # Настройка обработчика диалога
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            INITIAL: [MessageHandler(filters.Regex(r'^(Рассчитать сложный процент)$'), initial)],
            PRINCIPAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, principal)],
            MONTHLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, monthly)],
            RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, rate)],
            YEARS: [MessageHandler(filters.TEXT & ~filters.COMMAND, years)],
            WAIT_FOR_RESTART: [
                MessageHandler(filters.Regex(r'^(🔄 Новый расчет)$'), restart)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()