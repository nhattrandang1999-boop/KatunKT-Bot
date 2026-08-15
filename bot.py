import os
import threading
import sqlite3
import asyncio

from fastapi import FastAPI
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
PORT = int(os.environ.get("PORT", "10000"))

KLING_EMOJI_ID = "6053097225016321073"

app = FastAPI()

PRODUCTS = {
    "kling": {
        "name": "Kling 65 Credit",
        "price": 650,
        "stars": 10,
        "stock": 22,
    }
}


def database():
    conn = sqlite3.connect("shop.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product TEXT,
            payment TEXT,
            status TEXT
        )
    """)
    conn.commit()
    return conn


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(
    "Kling 65 Credit",
    callback_data="product:kling",
    icon_custom_emoji_id=KLING_EMOJI_ID,
            )
        ],
        [
            InlineKeyboardButton(
                "🧾 Đơn hàng",
                callback_data="orders"
            )
        ],
    ]

    await update.message.reply_text(
        "🛍️ KATUNAI SHOP\n\n"
        "Chào mừng bạn đến cửa hàng tài khoản AI.\n\n"
        "Chọn sản phẩm bên dưới:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "orders":
        conn = database()
        rows = conn.execute(
            "SELECT id, product, payment, status "
            "FROM orders WHERE user_id=? ORDER BY id DESC",
            (query.from_user.id,),
        ).fetchall()
        conn.close()

        if not rows:
            await query.message.reply_text(
                "🧾 Bạn chưa có đơn hàng."
            )
            return

        text = "🧾 ĐƠN HÀNG CỦA BẠN\n\n"

        for row in rows:
            text += (
                f"#{row[0]} | {row[1]} | "
                f"{row[2]} | {row[3]}\n"
            )

        await query.message.reply_text(text)
        return

    if query.data == "product:kling":
        product = PRODUCTS["kling"]

        keyboard = [
            [
                InlineKeyboardButton(
                    f"⭐ Mua bằng {product['stars']} Stars",
                    callback_data="buy:kling",
                )
            ],
            [
                InlineKeyboardButton(
                    "💳 Thanh toán VNĐ",
                    callback_data="vnd:kling",
                )
            ],
        ]

        await query.message.reply_text(
            "🎬 KLING 65 CREDIT\n\n"
            f"💰 Giá: {product['price']:,}đ\n"
            f"⭐ Telegram Stars: {product['stars']}\n"
            f"📦 Kho: {product['stock']}\n\n"
            "Chọn phương thức thanh toán:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if query.data == "vnd:kling":
        await query.message.reply_text(
            "💳 THANH TOÁN VNĐ\n\n"
            "Tính năng thanh toán ngân hàng đang ở chế độ TEST.\n"
            "Sau khi kết nối cổng thanh toán, bot sẽ tự xác nhận đơn."
        )
        return

    if query.data == "buy:kling":
        product = PRODUCTS["kling"]

        await context.bot.send_invoice(
            chat_id=query.from_user.id,
            title=product["name"],
            description="Kling 65 Credit",
            payload="kling",
            currency="XTR",
            prices=[
                LabeledPrice(
                    product["name"],
                    product["stars"]
                )
            ],
        )


async def precheckout(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.pre_checkout_query.answer(ok=True)


async def payment_success(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    payment = update.message.successful_payment

    conn = database()

    cursor = conn.execute(
        """
        INSERT INTO orders
        (user_id, product, payment, status)
        VALUES (?, ?, ?, ?)
        """,
        (
            update.effective_user.id,
            "Kling 65 Credit",
            "Telegram Stars",
            "PAID",
        ),
    )

    order_id = cursor.lastrowid

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ THANH TOÁN THÀNH CÔNG!\n\n"
        f"🧾 Mã đơn: #{order_id}\n"
        "🎬 Sản phẩm: Kling 65 Credit\n\n"
        "⚠️ Đây là bản TEST. "
        "Hệ thống giao tài khoản tự động sẽ được thêm ở bước tiếp theo."
    )


@app.get("/")
def home():
    return {
        "status": "online",
        "bot": "KatunaiBot"
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


async def start_bot():
    bot = Application.builder().token(BOT_TOKEN).build()

    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("products", products))

    bot.add_handler(
        CallbackQueryHandler(callback)
    )

    bot.add_handler(
        PreCheckoutQueryHandler(precheckout)
    )

    bot.add_handler(
        MessageHandler(
            filters.SUCCESSFUL_PAYMENT,
            payment_success
        )
    )

    await bot.initialize()

    if bot.post_init:
        await bot.post_init()

    # Xóa webhook cũ để chuyển sang polling
    await bot.bot.delete_webhook(drop_pending_updates=True)

    await bot.updater.start_polling(
        drop_pending_updates=True
    )

    await bot.start()

    print("🤖 TELEGRAM BOT ĐANG CHẠY...")

    try:
        await asyncio.Event().wait()

    finally:
        print("🛑 ĐANG DỪNG TELEGRAM BOT...")

        await bot.updater.stop()
        await bot.stop()

        if bot.post_stop:
            await bot.post_stop()

        await bot.shutdown()

@app.on_event("startup")
async def startup_event():
    print("🚀 ĐANG KHỞI ĐỘNG TELEGRAM BOT...")
    asyncio.create_task(start_bot())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT
    )
