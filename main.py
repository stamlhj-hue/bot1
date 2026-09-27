import discord
from discord.ext import commands
from discord import app_commands
import datetime
import io
import os

# ==============================
# الإعدادات
# ==============================

SUPPORT_ROLE_ID = 1435973250097348708
LOG_CHANNEL_ID = 1435972794046349314

TOKEN = os.getenv("TOKEN")

# ==============================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


def is_support(member):
    return (
        member.guild_permissions.administrator
        or any(role.id == SUPPORT_ROLE_ID for role in member.roles)
    )


async def send_log(guild, title, description):
    channel = guild.get_channel(LOG_CHANNEL_ID)

    if channel is None:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    await channel.send(embed=embed)


async def create_transcript(channel):
    messages = []

    async for message in channel.history(limit=None, oldest_first=True):
        content = message.content

        if message.attachments:
            content += " | مرفقات: " + ", ".join(
                attachment.url for attachment in message.attachments
            )

        messages.append(
            f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"{message.author}: {content}"
        )

    transcript = "\n".join(messages)

    return io.BytesIO(transcript.encode("utf-8"))


# ==============================
# Ticket Panel
# ==============================

class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="🎫 اختر نوع التذكرة",
        custom_id="ticket_type",
        options=[
            discord.SelectOption(
                label="الدعم الفني",
                emoji="🛠️",
                value="support"
            ),
            discord.SelectOption(
                label="الشراء والمتجر",
                emoji="🛒",
                value="shop"
            ),
            discord.SelectOption(
                label="شكوى",
                emoji="⚠️",
                value="complaint"
            ),
            discord.SelectOption(
                label="استفسار",
                emoji="❓",
                value="question"
            )
        ]
    )
    async def ticket_type(
        self,
        interaction: discord.Interaction,
        select: discord.ui.Select
    ):
        guild = interaction.guild
        user = interaction.user

        for channel in guild.text_channels:
            if channel.topic == f"ticket:{user.id}":
                await interaction.response.send_message(
                    f"❌ عندك تذكرة مفتوحة بالفعل: {channel.mention}",
                    ephemeral=True
                )
                return

        ticket_names = {
            "support": "دعم",
            "shop": "شراء",
            "complaint": "شكوى",
            "question": "استفسار"
        }

        ticket_type = ticket_names[select.values[0]]
        support_role = guild.get_role(SUPPORT_ROLE_ID)

        overwrites = {
            guild.default_role:
                discord.PermissionOverwrite(view_channel=False),

            user:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
        }

        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        channel = await guild.create_text_channel(
            name=f"{ticket_type}-{user.name}",
            topic=f"ticket:{user.id}",
            overwrites=overwrites
        )

        embed = discord.Embed(
            title="🎫 تم فتح التذكرة",
            description=(
                f"أهلًا {user.mention} 👋\n\n"
                f"**نوع التذكرة:** {ticket_type}\n\n"
                "اكتب مشكلتك هنا وسيقوم فريق الدعم بمساعدتك.\n\n"
                "استخدم الأزرار بالأسفل للتحكم بالتذكرة."
            ),
            color=discord.Color.green()
        )

        await channel.send(
            content=f"{user.mention} <@&{SUPPORT_ROLE_ID}>",
            embed=embed,
            view=TicketControls()
        )

        await send_log(
            guild,
            "🎫 Ticket Opened",
            f"**المستخدم:** {user.mention}\n"
            f"**التذكرة:** {channel.mention}\n"
            f"**النوع:** {ticket_type}"
        )

        await interaction.response.send_message(
            f"✅ تم فتح التذكرة: {channel.mention}",
            ephemeral=True
        )


# ==============================
# أزرار التذكرة
# ==============================

class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim",
        emoji="🙋",
        style=discord.ButtonStyle.blurple,
        custom_id="ticket_claim"
    )
    async def claim(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not is_support(interaction.user):
            await interaction.response.send_message(
                "❌ هذا الزر لفريق الدعم فقط.",
                ephemeral=True
            )
            return

        await interaction.channel.send(
            f"🙋 تم استلام التذكرة بواسطة {interaction.user.mention}"
        )

        await send_log(
            interaction.guild,
            "🙋 Ticket Claimed",
            f"**الموظف:** {interaction.user.mention}\n"
            f"**التذكرة:** {interaction.channel.mention}"
        )

        await interaction.response.send_message(
            "✅ تم استلام التذكرة.",
            ephemeral=True
        )

    @discord.ui.button(
        label="إضافة عضو",
        emoji="➕",
        style=discord.ButtonStyle.green,
        custom_id="ticket_add"
    )
    async def add_member(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not is_support(interaction.user):
            await interaction.response.send_message(
                "❌ لفريق الدعم فقط.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(AddMemberModal())

    @discord.ui.button(
        label="إزالة عضو",
        emoji="➖",
        style=discord.ButtonStyle.gray,
        custom_id="ticket_remove"
    )
    async def remove_member(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not is_support(interaction.user):
            await interaction.response.send_message(
                "❌ لفريق الدعم فقط.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(RemoveMemberModal())

    @discord.ui.button(
        label="تغيير الاسم",
        emoji="✏️",
        style=discord.ButtonStyle.blurple,
        custom_id="ticket_rename"
    )
    async def rename(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not is_support(interaction.user):
            await interaction.response.send_message(
                "❌ لفريق الدعم فقط.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(RenameModal())

    @discord.ui.button(
        label="إغلاق",
        emoji="🔒",
        style=discord.ButtonStyle.red,
        custom_id="ticket_close"
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not is_support(interaction.user):
            await interaction.response.send_message(
                "❌ لفريق الدعم فقط.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "🔒 سيتم حفظ الـ Transcript وإغلاق التذكرة..."
        )

        transcript = await create_transcript(
            interaction.channel
        )

        log_channel = interaction.guild.get_channel(
            LOG_CHANNEL_ID
        )

        if log_channel:
            await log_channel.send(
                content=(
                    f"📄 **Transcript**\n"
                    f"التذكرة: `{interaction.channel.name}`\n"
                    f"بواسطة: {interaction.user.mention}"
                ),
                file=discord.File(
                    transcript,
                    filename=f"{interaction.channel.name}.txt"
                )
            )

        await send_log(
            interaction.guild,
            "🔒 Ticket Closed",
            f"**التذكرة:** `{interaction.channel.name}`\n"
            f"**بواسطة:** {interaction.user.mention}"
        )

        await discord.utils.sleep_until(
            discord.utils.utcnow()
            + datetime.timedelta(seconds=3)
        )

        await interaction.channel.delete()

    @discord.ui.button(
        label="حذف",
        emoji="🗑️",
        style=discord.ButtonStyle.gray,
        custom_id="ticket_delete"
    )
    async def delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not is_support(interaction.user):
            await interaction.response.send_message(
                "❌ لفريق الدعم فقط.",
                ephemeral=True
            )
            return

        await send_log(
            interaction.guild,
            "🗑️ Ticket Deleted",
            f"**التذكرة:** `{interaction.channel.name}`\n"
            f"**بواسطة:** {interaction.user.mention}"
        )

        await interaction.response.send_message(
            "🗑️ سيتم حذف التذكرة..."
        )

        await discord.utils.sleep_until(
            discord.utils.utcnow()
            + datetime.timedelta(seconds=2)
        )

        await interaction.channel.delete()


# ==============================
# إضافة عضو
# ==============================

class AddMemberModal(
    discord.ui.Modal,
    title="إضافة عضو"
):
    user_id = discord.ui.TextInput(
        label="ID العضو",
        placeholder="ضع Discord ID هنا",
        required=True
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        try:
            member = interaction.guild.get_member(
                int(self.user_id.value)
            )

            if member is None:
                await interaction.response.send_message(
                    "❌ لم أجد هذا العضو.",
                    ephemeral=True
                )
                return

            await interaction.channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

            await interaction.response.send_message(
                f"✅ تمت إضافة {member.mention} للتذكرة."
            )

        except ValueError:
            await interaction.response.send_message(
                "❌ الـ ID غير صحيح.",
                ephemeral=True
            )


# ==============================
# إزالة عضو
# ==============================

class RemoveMemberModal(
    discord.ui.Modal,
    title="إزالة عضو"
):
    user_id = discord.ui.TextInput(
        label="ID العضو",
        placeholder="ضع Discord ID هنا",
        required=True
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        try:
            member = interaction.guild.get_member(
                int(self.user_id.value)
            )

            if member is None:
                await interaction.response.send_message(
                    "❌ لم أجد هذا العضو.",
                    ephemeral=True
                )
                return

            await interaction.channel.set_permissions(
                member,
                overwrite=None
            )

            await interaction.response.send_message(
                f"✅ تمت إزالة {member.mention} من التذكرة."
            )

        except ValueError:
            await interaction.response.send_message(
                "❌ الـ ID غير صحيح.",
                ephemeral=True
            )


# ==============================
# تغيير الاسم
# ==============================

class RenameModal(
    discord.ui.Modal,
    title="تغيير اسم التذكرة"
):
    new_name = discord.ui.TextInput(
        label="الاسم الجديد",
        placeholder="مثال: مشكلة-شراء",
        max_length=50,
        required=True
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        await interaction.channel.edit(
            name=self.new_name.value
        )

        await interaction.response.send_message(
            f"✅ تم تغيير الاسم إلى `{self.new_name.value}`."
        )


# ==============================
# أمر Ticket Panel
# ==============================

@bot.tree.command(
    name="ticket-panel",
    description="إرسال بانل التذاكر"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def ticket_panel(
    interaction: discord.Interaction
):
    embed = discord.Embed(
        title="🎫 الدعم الفني",
        description=(
            "مرحبًا بك في نظام التذاكر.\n\n"
            "اختر نوع التذكرة من القائمة بالأسفل "
            "وسيتم إنشاء روم خاص لك وللدعم."
        ),
        color=discord.Color.green()
    )

    embed.add_field(
        name="🛠️ الدعم الفني",
        value="للمشاكل التقنية",
        inline=False
    )

    embed.add_field(
        name="🛒 المتجر",
        value="للشراء والطلبات",
        inline=False
    )

    embed.add_field(
        name="⚠️ الشكاوى",
        value="لتقديم شكوى",
        inline=False
    )

    embed.add_field(
        name="❓ الاستفسارات",
        value="للاستفسارات العامة",
        inline=False
    )

    await interaction.channel.send(
        embed=embed,
        view=TicketPanel()
    )

    await interaction.response.send_message(
        "✅ تم إرسال Ticket Panel.",
        ephemeral=True
    )


# ==============================
# Ping
# ==============================

@bot.tree.command(
    name="ping",
    description="معرفة سرعة البوت"
)
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)

    await interaction.response.send_message(
        f"🏓 Pong!\n`{latency}ms`"
    )


# ==============================
# تشغيل البوت
# ==============================

@bot.event
async def on_ready():
    bot.add_view(TicketPanel())
    bot.add_view(TicketControls())

    await bot.tree.sync()

    print(f"✅ تم تشغيل البوت: {bot.user}")


if not TOKEN:
    raise RuntimeError(
        "لم يتم العثور على TOKEN في Environment Variables"
    )

bot.run(TOKEN)
