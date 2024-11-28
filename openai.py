@router.message(Command("summarise"))
async def summarise_messages(message: Message):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Извлекаем последние 100 сообщений из базы данных
        cur.execute("""
            SELECT user_name, message 
            FROM messages 
            WHERE chat_id = %s 
            ORDER BY id DESC 
            LIMIT 100
        """, (message.chat.id,))
        rows = cur.fetchall()

        if not rows:
            await message.reply("Сообщений пока нет.")
            return

        # Переворачиваем порядок сообщений, чтобы они шли от старых к новым
        rows.reverse()

        # Формируем контекст для OpenAI
        conversation = "\n".join([f"{row['user_name']}: {row['message']}" for row in rows])

        # Запрос к OpenAI
        prompt = (
            "Ниже приведен диалог между участниками чата. Подведи итог, что обсуждалось, какие идеи высказывались и какие выводы были сделаны.\n\n"
            f"{conversation}\n\n"
            "Итог:"
        )

        try:
            response = openai.Completion.create(
                model="text-davinci-003",
                prompt=prompt,
                temperature=0.5,
                max_tokens=300,
            )
            summary = response.choices[0].text.strip()
            await message.reply(f"Вот итог обсуждения:\n\n{summary}")
        except Exception as e:
            logging.error(f"Ошибка при обращении к OpenAI: {e}")
            await message.reply("Не удалось получить итог. Попробуйте позже.")
    except Exception as e:
        logging.error(f"Ошибка при составлении итогов: {e}")
        await message.reply("Ошибка при составлении итогов.")
    finally:
        cur.close()
        conn.close()
