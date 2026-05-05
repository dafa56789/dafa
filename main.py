import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("Thiếu BOT_TOKEN trong Railway Variables")

TOKEN = TOKEN.strip()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot đã hoạt động 🚀")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Các lệnh có sẵn:\n/start\n/help")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))

print("Bot đang chạy...")

app.run_polling()
import os
import re
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    filters, ContextTypes
)
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    DateTime, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker

# ================= DB =================
engine = create_engine("sqlite:///bot.db")
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    group_id = Column(String)
    user = Column(String)
    amount = Column(Float)
    raw = Column(Float)
    type = Column(String)  # in/out
    rate = Column(Float, default=1)
    fee = Column(Float, default=0)
    team_id = Column(Integer, default=0)
    status = Column(String, default="active")  # active/deleted
    created_at = Column(DateTime, default=datetime.utcnow)

class Operator(Base):
    __tablename__ = "operators"
    id = Column(Integer, primary_key=True)
    group_id = Column(String)
    user_id = Column(String)
    is_admin = Column(Boolean, default=False)

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    group_id = Column(String)
    name = Column(String)
    active = Column(Boolean, default=True)

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    group_id = Column(String)
    action = Column(String)
    actor = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

# ================= BOT =================
TOKEN = os.getenv("TOKEN")

def log(group_id, actor, action):
    l = Log(group_id=group_id, actor=actor, action=action)
    session.add(l)
    session.commit()

def is_operator(group_id, user_id):
    return session.query(Operator)\
        .filter_by(group_id=group_id, user_id=str(user_id))\
        .first() is not None

def add_operator(group_id, user_id, admin=False):
    op = session.query(Operator)\
        .filter_by(group_id=group_id, user_id=str(user_id))\
        .first()
    if not op:
        op = Operator(group_id=group_id, user_id=str(user_id), is_admin=admin)
        session.add(op)
        session.commit()

def parse_in(text, sender):
    # 张三+1000u/7.3*0.1 备注
    pattern = r"(?:(\w+))?\+(\d+)(?:u)?(?:/(\d+\.?\d*))?(?:\*(\d+\.?\d*))?\s*(.*)"
    m = re.match(pattern, text)
    if not m:
        return None
    user = m.group(1) or sender
    raw = float(m.group(2))
    rate = float(m.group(3)) if m.group(3) else 1
    fee = float(m.group(4)) if m.group(4) else 0
    note = m.group(5)
    final = (raw / rate) * (1 - fee)
    return user, raw, final, rate, fee, note

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = str(update.effective_chat.id)
    uid = str(update.effective_user.id)
    add_operator(gid, uid, admin=True)  # người đầu tiên thành admin
    await update.message.reply_text("📊 记账机器人已启动（你是管理员）")

# ================= HANDLER =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    gid = str(update.effective_chat.id)
    uid = str(update.effective_user.id)
    sender = update.effective_user.first_name

    # ===== 添加操作人（admin）=====
    if text.startswith("添加操作人"):
        if not is_operator(gid, uid):
            return
        add_operator(gid, uid)  # thêm chính người gửi (đơn giản)
        await update.message.reply_text("✅ 已添加操作人")
        return

    # ===== TEAM =====
    if text.startswith("创建团队"):
        if not is_operator(gid, uid): return
        name = text.replace("创建团队", "").strip()
        t = Team(group_id=gid, name=name)
        session.add(t); session.commit()
        log(gid, sender, f"创建团队 {name}")
        await update.message.reply_text(f"👥 已创建团队: {name}")
        return

    if text == "团队列表":
        teams = session.query(Team).filter_by(group_id=gid, active=True).all()
        msg = "👥 团队:\n" + "\n".join([f"- {t.name}" for t in teams]) if teams else "暂无团队"
        await update.message.reply_text(msg)
        return

    # ===== PERMISSION =====
    if not is_operator(gid, uid):
        return

    # ===== 入账 =====
    data = parse_in(text, sender)
    if data:
        user, raw, final, rate, fee, note = data
        tx = Transaction(
            group_id=gid, user=user, amount=final, raw=raw,
            type="in", rate=rate, fee=fee
        )
        session.add(tx); session.commit()
        log(gid, sender, f"入账 {user} +{raw} => {round(final,2)}")
        await update.message.reply_text(
            f"✅ 入账\n{user} +{raw}\n实际:{round(final,2)}"
        )
        return

    # ===== 下发 =====
    m = re.match(r"(?:(\w+))?下发(\d+)", text)
    if m:
        user = m.group(1) or sender
        amount = float(m.group(2))
        tx = Transaction(group_id=gid, user=user, amount=amount, raw=amount, type="out")
        session.add(tx); session.commit()
        log(gid, sender, f"下发 {user} -{amount}")
        await update.message.reply_text(f"📤 下发 {user} -{amount}")
        return

    # ===== 汇总 =====
    if text in ["总", "账单汇总"]:
        ins = sum(t.amount for t in session.query(Transaction)
                  .filter_by(group_id=gid, type="in", status="active"))
        outs = sum(t.amount for t in session.query(Transaction)
                   .filter_by(group_id=gid, type="out", status="active"))
        await update.message.reply_text(
            f"📊 汇总\n入款:{ins}\n下发:{outs}\n余额:{ins-outs}"
        )
        return

    # ===== 历史 =====
    if text in ["显示账单", "+0"]:
        txs = session.query(Transaction)\
            .filter_by(group_id=gid, status="active")\
            .order_by(Transaction.id.desc()).limit(10).all()
        if not txs:
            await update.message.reply_text("📭 没有账单")
            return
        msg = "📜 最近账单:\n"
        for t in txs:
            sign = "+" if t.type == "in" else "-"
            msg += f"{t.id}. {t.user} {sign}{t.amount}\n"
        await update.message.reply_text(msg)
        return

    # ===== 撤销（最后一条）=====
    if text == "撤销":
        tx = session.query(Transaction)\
            .filter_by(group_id=gid, status="active")\
            .order_by(Transaction.id.desc()).first()
        if tx:
            tx.status = "deleted"; session.commit()
            log(gid, sender, f"撤销 #{tx.id}")
            await update.message.reply_text("↩️ 已撤销")
        return

    # ===== 撤销入款 / 下发 =====
    if text == "撤销入款":
        tx = session.query(Transaction)\
            .filter_by(group_id=gid, type="in", status="active")\
            .order_by(Transaction.id.desc()).first()
        if tx:
            tx.status = "deleted"; session.commit()
            log(gid, sender, f"撤销入款 #{tx.id}")
            await update.message.reply_text("↩️ 已撤销入款")
        return

    if text == "撤销下发":
        tx = session.query(Transaction)\
            .filter_by(group_id=gid, type="out", status="active")\
            .order_by(Transaction.id.desc()).first()
        if tx:
            tx.status = "deleted"; session.commit()
            log(gid, sender, f"撤销下发 #{tx.id}")
            await update.message.reply_text("↩️ 已撤销下发")
        return

    # ===== 回复撤销（按ID）=====
    if update.message.reply_to_message and text == "撤销":
        replied = update.message.reply_to_message.text or ""
        m = re.search(r"(\d+)\.", replied)  # bắt id từ dòng "12. 张三 +100"
        if m:
            tx_id = int(m.group(1))
            tx = session.query(Transaction)\
                .filter_by(id=tx_id, group_id=gid).first()
            if tx and tx.status == "active":
                tx.status = "deleted"; session.commit()
                log(gid, sender, f"回复撤销 #{tx.id}")
                await update.message.reply_text("↩️ 已撤销该记录")
        return

    # ===== 删除 =====
    if text == "删除账单":
        tx = session.query(Transaction)\
            .filter_by(group_id=gid, status="active")\
            .order_by(Transaction.id.desc()).first()
        if tx:
            tx.status = "deleted"; session.commit()
            log(gid, sender, f"删除 #{tx.id}")
            await update.message.reply_text("🗑 已删除最后一条")
        return

    if text == "删除全部账单":
        session.query(Transaction)\
            .filter_by(group_id=gid)\
            .update({Transaction.status: "deleted"})
        session.commit()
        log(gid, sender, "删除全部账单")
        await update.message.reply_text("🗑 已清空")
        return

    # ===== 日志 =====
    if text == "操作日志":
        logs = session.query(Log)\
            .filter_by(group_id=gid)\
            .order_by(Log.id.desc()).limit(10).all()
        msg = "📜 日志:\n" + "\n".join([f"{l.actor}: {l.action}" for l in logs]) if logs else "暂无日志"
        await update.message.reply_text(msg)
        return

# ================= RUN =================
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, handle))

print("Bot running...")
app.run_polling()
