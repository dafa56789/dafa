from database import SessionLocal, Memory

def save_memory(user_id, text):
    db = SessionLocal()
    memory = Memory(user_id=user_id, content=text)
    db.add(memory)
    db.commit()
    db.close()


def get_memories(user_id, limit=5):
    db = SessionLocal()
    memories = (
        db.query(Memory)
        .filter(Memory.user_id == user_id)
        .order_by(Memory.id.desc())
        .limit(limit)
        .all()
    )
    db.close()
    return [m.content for m in memories]
