"""
-*- coding: utf-8 -*-
@File  : Missed_Task_Lambda_Function.py
@author: mingyu110
@Description : 
@Time  : 2024/07/01
"""
import pymysql
import json
import os
import requests
import datetime


def lambda_handler(event, context):
    # Database connection details
    rds_host = os.environ['RDS_HOST']
    rds_username = os.environ['RDS_USERNAME']
    rds_password = os.environ['RDS_PASSWORD']
    rds_db_name = os.environ['RDS_DB_NAME']

    # Telegram Bot API details
    telegram_token = os.environ['TELEGRAM_TOKEN']

    # Connect to the database
    connection = pymysql.connect(
        host=rds_host,
        user=rds_username,
        password=rds_password,
        db=rds_db_name
    )

    try:
        with connection.cursor() as cursor:
            # Get all pending notifications older than 2 minutes
            two_minutes_ago = (datetime.datetime.now() - datetime.timedelta(minutes=2)).strftime('%Y-%m-%d %H:%M:%S')
            sql = """
            SELECT id, user_id, phone_number, task_name, notification_timestamp 
            FROM taskreminder 
            WHERE notification_status = 'pending' AND notification_timestamp <= %s
            """
            cursor.execute(sql, (two_minutes_ago,))
            results = cursor.fetchall()

            # Debugging: Print results
            print("Results: ", results)

            for result in results:
                try:
                    task_id = result[0]
                    user_id = result[1]
                    chat_id = result[2]
                    task_name = result[3]
                    # notification_timestamp = result[4]

                    # Check the last message from the user
                    last_message = get_last_message(telegram_token, chat_id)

                    if last_message:
                        text = last_message['text'].strip().lower()

                        if text == 'yes':
                            # Update the notification status to confirmed and increment the user's score
                            update_task_sql = """
                            UPDATE taskreminder
                            SET notification_status = 'confirmed' 
                            WHERE id = %s
                            """
                            update_user_sql = """
                            UPDATE users 
                            SET user_score = user_score + 1 
                            WHERE id = %s
                            """
                            cursor.execute(update_task_sql, (task_id,))
                            cursor.execute(update_user_sql, (user_id,))
                            connection.commit()
                            send_telegram_message(telegram_token, chat_id,
                                                  f"Great! You've confirmed taking your {task_name}.Your score has "
                                                  f"been increased by 1.")
                        elif text == 'no':
                            # Update the notification status to missed and decrement the user's score
                            update_task_sql = """
                            UPDATE taskreminder
                            SET notification_status = 'missed' 
                            WHERE id = %s
                            """
                            update_user_sql = """
                            UPDATE users 
                            SET user_score = user_score - 1 
                            WHERE id = %s
                            """
                            cursor.execute(update_task_sql, (task_id,))
                            cursor.execute(update_user_sql, (user_id,))
                            connection.commit()
                            send_telegram_message(telegram_token, chat_id,
                                                  f"Please remember to take your {task_name} as soon as possible. "
                                                  f"Your score has been decreased by 1.")
                    else:
                        # No response within 2 minutes
                        update_task_sql = """
                        UPDATE taskreminder
                        SET notification_status = 'missed' 
                        WHERE id = %s
                        """
                        update_user_sql = """
                        UPDATE users 
                        SET user_score = user_score - 1 
                        WHERE id = %s
                        """
                        cursor.execute(update_task_sql, (task_id,))
                        cursor.execute(update_user_sql, (user_id,))
                        connection.commit()
                        send_telegram_message(telegram_token, chat_id,
                                              f"You missed taking your {task_name}. Your score has been decreased by "
                                              f"1. Please remember to take it as soon as possible.")
                except IndexError as e:
                    print(f"IndexError: {str(e)} - Result: {result}")

    except Exception as e:
        print(f"Error: {str(e)}")

    finally:
        connection.close()

    return {
        'statusCode': 200,
        'body': json.dumps('Response processed successfully!')
    }


def get_last_message(token, chat_id):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    response = requests.get(url)
    if response.status_code == 200:
        updates = response.json()['result']
        for update in reversed(updates):
            if 'message' in update and update['message']['chat']['id'] == chat_id:
                return update['message']
    return None


def send_telegram_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"Failed to send message: {response.text}")
    else:
        print(f"Sent message: {message}")
