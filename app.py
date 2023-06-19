
import re
import random
import sqlite3
import requests
from bs4 import BeautifulSoup
from googletrans import Translator
from flask import Flask, render_template, request, redirect


app = Flask(__name__)

def query_to_db(query, commit=False):
    with sqlite3.connect('words.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query)

        if commit:
            conn.commit()
        else:
            return cursor.fetchall()

query_to_db(
    '''CREATE TABLE IF NOT EXISTS words (
        word TEXT,
        translation TEXT,
        definition TEXT
    )''',
    commit=True
)
query_to_db(
    '''CREATE TABLE IF NOT EXISTS level (
        points INT,
        level INT
    )''',
    commit=True
)

if query_to_db('''SELECT COUNT(*) FROM level''')[0][0] == 0:
    query_to_db('''INSERT INTO level VALUES (0,0);''', commit=True)

def get_options(word, field):
    options = [[word, True],]
    options_sql_random = query_to_db(
        f'''SELECT {field} FROM words WHERE {field} != '{word}' ORDER BY RANDOM() LIMIT 3;'''
    )
    options += [[i[0], False] for i in options_sql_random]
    random.shuffle(options)

    return options

def get_word_definition(word):
    try:
        url = f"https://www.dictionary.com/browse/{word}"

        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")

        definition_element = soup.find("div", {"data-type": "word-definition-content"}).find("p")

        if definition_element:
            definition = definition_element.get_text().split(";")[0].strip()
        else:
            definition = ""
        
        return definition
    except:
        return ""

def get_translated_word(word):
    try:
        translator = Translator()
        translation = translator.translate(word, src='en', dest='uk')
        return translation.text
    except:
        return ""

def up_level():
    points, level = query_to_db('''SELECT * FROM level;''')[0]
    
    print(points, level)

    points += 1
    if points >= (level + 1) * 100:
        points -= (level + 1) * 100
        level += 1

    print(points, level)

    query_to_db(f'''UPDATE level SET points={points}, level={level}''', commit=True)

@app.route('/')
def main():
    return render_template("main.html")

@app.route('/add-word')
def add_word():
    return render_template("add_word.html")

@app.route('/validate-word', methods=["POST"])
def validate_word():
    word = request.form.get("word", "")

    data = {
        "word": word.lower().strip(),
        "translation": get_translated_word(word).lower().strip(),
        "definition": get_word_definition(word)
    }
    return render_template("validate_word.html", **data)

@app.route('/save-word', methods=["POST"])
def save_word():
    word = request.form.get("word", "").replace("'", "''").lower().strip()
    translation = request.form.get("translation", "").replace("'", "''").lower().strip()
    definition = request.form.get("definition", "").replace("'", "''").strip()

    query_to_db(
        f'''INSERT INTO words (word, translation, definition) 
        VALUES ('{word}', '{translation}', '{definition}')''',
        commit=True
    )

    data = {
        "success": True
    }
    return render_template("add_word.html", **data)

@app.route('/see-words')
def see_words():
    page = request.args.get('page', 1, type=int)
    items_per_page = 10
    offset = (page - 1) * items_per_page

    words = query_to_db(f"SELECT * FROM words ORDER BY ROWID DESC LIMIT {items_per_page} OFFSET {offset};")
    total_items = query_to_db("SELECT COUNT(*) FROM words;")[0][0]
    total_pages = int(total_items / items_per_page) + (total_items % items_per_page > 0)

    data = {
        "words": words,
        "page": page,
        "total_pages": total_pages
    }
    
    return render_template("see_words.html", **data)

@app.route('/learn-words-levels')
def learn_words_levels():
    return render_template("learn_words_levels.html")

@app.route('/learn-words/<int:count>')
def learn_words(count):
    return redirect(
        random.choice([
            f"/learn-words/{count}/ua-eng",
            f"/learn-words/{count}/definition-eng",
            f"/learn-words/{count}/eng-ua",
            f"/learn-words/{count}/eng-ua-options",
            f"/learn-words/{count}/ua-eng-options",
            f"/learn-words/{count}/definition-eng-options",
            f"/learn-words/{count}/word",
        ])
    )

@app.route("/learn-words/<int:count>/<string:mode>/check", methods=["POST",])
def learn_words_check(count, mode):
    answer = request.form.get("answer", "").lower().strip()

    word = request.form.get("word", "")
    translation = request.form.get("translation", "")
    definition = request.form.get("definition", "")

    match mode:
        case "ua-eng" | "definition-eng" | "ua-eng-options" | "definition-eng-options":
            right_word = word
        case "eng-ua" | "eng-ua-options":
            right_word = translation
    
    if answer == right_word:
        up_level()
        return redirect(f"/learn-words/{count}")
    
    data = {
        "word": [word, translation, definition],
        "count": count
    }
    return render_template("learn_words_mistake.html", **data)

@app.route('/learn-words/<int:count>/<string:mode>')
def learn(count, mode):
    if count == 0:
        word = query_to_db('''SELECT * FROM words ORDER BY RANDOM() LIMIT 1;''')[0]
    else:
        word = query_to_db(
            f'''SELECT * FROM (
            SELECT * FROM words ORDER BY ROWID DESC LIMIT {count}
            ) ORDER BY RANDOM() LIMIT 1;
            '''
        )[0]

    match mode:
        case "ua-eng":
            return render_template("learn_ua_eng.html", word=word, count=count)
        case "definition-eng":
            return render_template("learn_definition_eng.html", word=word, count=count)
        case "eng-ua":
            return render_template("learn_eng_ua.html", word=word, count=count)
        case "eng-ua-options":    
            options = get_options(word[1], "translation")
            return render_template("learn_eng_ua_options.html", word=word, count=count, options=options)
        case "ua-eng-options":    
            options = get_options(word[0], "word")
            return render_template("learn_ua_eng_options.html", word=word, count=count, options=options)
        case "definition-eng-options":    
            options = get_options(word[0], "word")
            return render_template("learn_definition_eng_options.html", word=word, count=count, options=options)
        case "word":
            up_level()
            return render_template("learn_word.html", word=word, count=count)

@app.route('/statistics')
def statistics():
    points, level = query_to_db('''SELECT * FROM level;''')[0]
    count = query_to_db('''SELECT COUNT(*) FROM words;''')[0][0]

    data = {
        "level": level,
        "points": points,
        "next_level_points": (level + 1) * 100,
        "count": count
    }

    return render_template("statistics.html", **data)

if __name__ == '__main__':
    app.run(debug=True)
