import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from config import BOT_TOKEN
import data_fetcher

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Anna's Archive Bot!\n\n"
        "Send me a book title, author, or ISBN to search."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    if not query:
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # Perform search
    results = await asyncio.to_thread(data_fetcher.search_books, query)
    
    if not results:
        await update.message.reply_text("No results found. Try a different query.")
        return

    # Store results in user_data to access later if needed (optional, but good for pagination)
    # For now, we just list top 5 results
    context.user_data['results'] = results

    keyboard = []
    response_text = "📚 *Results:*\n\n"
    
    for i, book in enumerate(results[:5]):
        title = book['title'][:45] + "…" if len(book['title']) > 45 else book['title']
        author = book['author'][:25] if book['author'] != "Unknown Author" else ""
        year = book.get('year', '')
        ext = book.get('extension', '')
        
        # Build clean info line: Author (Year) · EXT
        info_parts = []
        if author:
            info_parts.append(author)
        if year:
            info_parts.append(f"({year})")
        if ext:
            info_parts.append(ext)
        
        info_line = " · ".join(info_parts) if info_parts else ""
        
        if info_line:
            response_text += f"{i+1}. *{title}* - {info_line}\n"
        else:
            response_text += f"{i+1}. *{title}*\n"
        keyboard.append([InlineKeyboardButton(f"⬇️ {i+1}", callback_data=f"dl_{book['md5']}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith("dl_"):
        md5 = data.split("_")[1]
        
        # Keep buttons to allow multiple downloads or re-clicks
        # await query.edit_message_reply_markup(reply_markup=None) 
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        
        links = await asyncio.to_thread(data_fetcher.get_download_links, md5)
        
        if not links:
            await query.message.reply_text("❌ Could not retrieve download links.")
            return
            
        # Format links
        text = "⬇️ **Download Links:**\n\n"
        
        if links:
            text += "**Slow Partner Servers:** (Waitlist/Verification)\n"
            for name, url in links.items():
                text += f"- [{name}]({url})\n"
        else:
             text += "No Slow Partner links found."
                
        await query.message.reply_text(text, parse_mode='Markdown', disable_web_page_preview=True)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

if __name__ == '__main__':
    if BOT_TOKEN == "YOUR_BOT_TOKEN":
        print("❌ Please set your BOT_TOKEN in config.py")
        exit(1)
        
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_error_handler(error_handler)
    
    print("Bot is running...")
    application.run_polling()
