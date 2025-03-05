from flask import Flask, request, jsonify
from collections import Counter
import Levenshtein, os, nltk, spacy
from nltk.tokenize import word_tokenize, RegexpTokenizer
from nltk.corpus import stopwords
import logging

# Set up logging configuration
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

nltk.download('stopwords')
nltk.download('punkt')  # Para tokenización

app = Flask(__name__)

dictionaries = {}
language_profiles = {}

def load_dic(file_path, dic_name):
    """Loads a dictionary file into the dictionaries dictionary."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            dictionaries[dic_name] = set(line.strip() for line in f)
        logging.info(f"Dictionary '{dic_name}' loaded successfully from {file_path}")
    except Exception as e:
        logging.error(f"Error loading dictionary '{dic_name}' from {file_path}: {e}")

def load_all_dics():
    """Loads all dictionary files from the 'dic' folder."""
    directory = "dic"
    if not os.path.exists(directory):
        logging.error("❌ Dictionary folder not found! Exiting.")
        exit(1)  # Stop execution

    filenames = os.listdir(directory)
    logging.info(f"Found {len(filenames)} dictionary files to load.")
    for file in filenames:
        file_path = os.path.join(directory, file)
        dic_name, _ = os.path.splitext(file)
        load_dic(file_path, dic_name)

def generate_ngrams(text, n=3):
    """Generates trigrams from text."""
    logging.debug(f"Generating {n}-grams for text: {text[:30]}...")  # Show only first 30 chars for brevity
    text = text.lower()
    text = ''.join([c for c in text if c.isalpha() or c.isspace()])
    ngrams = [text[i:i+n] for i in range(len(text)-n+1)]
    return Counter(ngrams)

def load_all_trigrams():
    """Loads trigrams for all dictionaries."""
    if not dictionaries:
        logging.error("❌ No dictionaries loaded, skipping trigram generation!")
        return

    logging.info("Generating trigrams for all dictionaries...")
    for dic_name, words in dictionaries.items():
        text = " ".join(words)
        language_profiles[dic_name] = generate_ngrams(text)
        logging.info(f"Trigrams for dictionary '{dic_name}' generated successfully.")

def proportion_similarity(profile1, profile2):
    """Computes similarity proportion between two trigram profiles."""
    intersection = set(profile1.keys()) & set(profile2.keys())
    matches = sum(profile1[ngram] for ngram in intersection)
    total = sum(profile1.values())
    similarity = matches / total if total > 0 else 0.0
    logging.debug(f"Calculated proportion similarity: {similarity}")
    return similarity

def correct_word(word, dictionary):
    """Finds the closest word using Levenshtein distance."""
    min_distance = float('inf')
    corrected_word = word

    logging.debug(f"Correcting word: {word}")
    for dict_word in dictionary:
        distance = Levenshtein.distance(word, dict_word)
        if distance < min_distance:
            min_distance = distance
            corrected_word = dict_word

    logging.info(f"Corrected word '{word}' to '{corrected_word}'")
    return corrected_word

def fix_text(text, dictionary):
    """Corrects words in a given text based on a dictionary."""
    words = text.split()
    corrected_words = [correct_word(word, dictionary) for word in words]
    return " ".join(corrected_words)

# Load dictionaries and trigrams when the server starts
load_all_dics()
load_all_trigrams()

@app.route('/get_language_text', methods=['POST'])
def detect_language():
    """Detects language of the input text using trigram similarity."""
    data = request.json
    if not data or "text" not in data:
        logging.warning("No text provided in the request.")
        return jsonify({"error": "No text provided"}), 400
    
    text = data["text"]
    text_profile = generate_ngrams(text, n=3)

    similarities = {lang: proportion_similarity(text_profile, profile) for lang, profile in language_profiles.items()}
    
    if not similarities:  # Check if empty
        logging.warning("No language profiles available to compare.")
        return jsonify({"error": "No language profiles available"}), 500

    detected_language = max(similarities, key=similarities.get)
    logging.info(f"Detected language: {detected_language} with similarities: {similarities}")
    
    return jsonify({
        "detected_language": detected_language,
        "coincidences": similarities
    }), 200

@app.route("/fix_words", methods=['POST'])
def fix_words():
    """Corrects misspelled words in the input text based on the specified language dictionary."""
    if not dictionaries:  # Ensure dictionaries exist
        logging.error("No dictionaries available for word correction.")
        return jsonify({"error": "No dictionaries available"}), 500

    data = request.get_json()
    if not data or "text" not in data or "lang" not in data:
        logging.warning("No text or language specified in the request.")
        return jsonify({"error": "No information provided"}), 400
    
    text = data["text"]
    language = data["lang"]
    
    if language not in dictionaries:
        logging.warning(f"Unsupported language: {language}")
        return jsonify({"error": "Unsupported language"}), 400
    
    correct_text = fix_text(text, dictionaries[language])
    logging.info(f"Fixed text for language '{language}': {correct_text[:30]}...")  # Show only first 30 chars
    
    return jsonify({"text": correct_text}), 200

@app.route("/tokenize", methods=['POST'])
def tokenize():
    data = request.get_json()
    if not data or "text" not in data:
        logging.warning("No text provided in the request for tokenization.")
        return jsonify({"error": "No information provided"}), 400
    
    text = data["text"]
    tokenizer = RegexpTokenizer(r'\w+')
    tokens = tokenizer.tokenize(text)
    tokenized_text = "\n".join(tokens)

    logging.info(f"Tokenized text: {tokenized_text[:30]}...")  # Show only first 30 chars

    return jsonify({"tokens": tokenized_text}), 200

@app.route("/remove_stopwords", methods=['POST'])
@app.route("/remove_stopwords", methods=['POST'])
def remove_stopwords():
    data = request.get_json()
    if not data or "tokens" not in data or "lang" not in data:
        logging.warning("No tokens or language specified in the request for stopword removal.")
        return jsonify({"error": "No information provided"}), 400
    
    tokens = data["tokens"]
    lang = data["lang"]

    if isinstance(tokens, str):
        tokens = tokens.split("\n")  # Convert back to list

    try:
        stop_words = set(stopwords.words(lang))
    except OSError:
        return jsonify({"error": f"Unsupported language: {lang}"}), 400
        logging.warning("{lang} unsupported")
    # Remove stopwords
    filtered_tokens = [word for word in tokens if word.lower() not in stop_words]
    cleaned_text = "\n".join(filtered_tokens)

    logging.info(f"Removed stopwords. Cleaned text: {cleaned_text[:30]}...")  # Show only first 30 chars

    return jsonify({"text": cleaned_text}), 200
@app.route("/get_lemmas", methods=['POST'])
def get_lemmas():
    data = request.get_json()
    
    if not data or "text" not in data or "lang" not in data:
        logging.warning("No text or language specified for lemmatization.")
        return jsonify({"error": "No text or language provided"}), 400

    text = data["text"]
    lang = data["lang"]

    # Supported spaCy language models
    supported_models = {
        "english": "en_core_web_sm",
        "spanish": "es_core_news_sm",
        "french": "fr_core_news_sm",
        "dutch": "de_core_news_sm",
        "italian": "it_core_news_sm",
        "portuguese": "pt_core_news_sm"
    }

    # Check if the language is supported
    if lang not in supported_models:
        logging.warning(f"Unsupported language for lemmatization: {lang}")
        return jsonify({"error": "Unsupported language"}), 400

    try:
        nlp = spacy.load(supported_models[lang])
    except Exception as e:
        logging.error(f"Error loading spaCy model for '{lang}': {e}")
        return jsonify({"error": "Failed to load language model"}), 500

    # Process the text
    doc = nlp(text)
    lemmatized_tokens = [{"token": token.text, "lemma": token.lemma_} for token in doc]

    logging.info(f"Lemmatized text for {lang}: {lemmatized_tokens[:3]}...")  # Show first 3 tokens

    return jsonify({"lemmas": lemmatized_tokens}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5001)
