# Importing the required libraries
import torch
import pandas as pd
import matplotlib.pyplot as plt
import os
import seaborn as sns
from sklearn.model_selection import train_test_split
import nltk
from nltk.tokenize import word_tokenize
from collections import Counter
import re
import torch
from torchtext.vocab import vocab
from torch.utils.data import Dataset
from nltk.stem import WordNetLemmatizer
import subprocess

nltk.download("punkt")
nltk.download('wordnet')


#------------------------------------------------------------------------------
# Function Definitions
def rating_to_sentiment(rating):
    """
    Parameters
    ----------
    rating : int
        The star rating of the item from 1 to 5.

    Returns
    -------
    sentiment : int
        Implied sentiment of the star rating, assumes ratings between 1 and 3 (inclusive) to be
        negative (0) and rating more than 3 to be positive (1).
    """
    
    if rating in {1, 2, 3}:
        return 0
    else:
        return 1

def cleanup_text(text):
    """
    Performs the following tasks on the text:
        - lowercasing all the characters
        - removing non-alphabet characters excluding "., !, (, ), \n, :, ?"
        - removing any multiple consecutive occurence of the excluded characters above
    
    Parameters
    ----------
    text : str
        text to be cleaned.

    Returns
    -------
    text : str
        cleaned text.
    """
    
    text = text.lower()
    text = re.sub(r"[^a-z.?!:)( \n]+", "", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\.{2,}", "!", text)
    text = re.sub(r"\.{2,}", "?", text)
    text = re.sub(r"\.{2,}", ")", text)
    text = re.sub(r"\.{2,}", "(", text)
    text = re.sub(r"\.{2,}", ":", text)
    return text

def create_vocab(text, tokenizer, lemmatizer, unk_token, pad_token):
    """
    Creates a vocabulary based on the input text corpus that assigns an index 
    to each token.

    Parameters
    ----------
    text : str
        The text corpus used for token extraction.
    tokenizer : obj
        Tokenizer object for tokenization of the text.
    lemmatizer : obj
        Lemmantizer onject for Llmmantization of the text.
    unk_token : str
        The symbol used for out of vocabulary tokens.
    pad_token : str
        The symbol used for displaying the padded indices of the sentences.

    Returns
    -------
    vocabulary : TYPE
        DESCRIPTION.

    """
    
    # Tookenizing the text
    tokenized_text = tokenizer(text)
    # Lemmantizing the text
    lemmatized_text = [lemmatizer.lemmatize(word) for word in tokenized_text]
    # Creating a hash map counting the instances of each token
    token_freqs = Counter(lemmatized_text)
    # Creating a vocabulary 
    vocabulary = vocab(token_freqs, min_freq = 10, specials = [pad_token, unk_token])
    # Setting the index that should be assigned to OOV tokens.
    vocabulary.set_default_index(1)
    return vocabulary

def process_reviews(review, tokenizer, lemmatizer, vocabulary, max_len):
    """
    Performs the following tasks on each review text:
        - cleaning the text
        - tokenizing the text
        - lemmantizing the text
        - converting the tokens into indices 
        - padding and truncating the review based on max_len passed to the function

    Parameters
    ----------
    review : str
        The product review text.
    tokenizer : obj
        Tokenizer object for tokenization of the text.
    lemmatizer : obj
        Lemmantizer onject for Llmmantization of the text.
    vocabulary : obj
        Vocabulary object correspoding tokens and indices.
    max_len : int
        Maximum allowed length of a product review.

    Returns
    -------
    review_processed : list
        A list of indices.
    """
    
    review_cleaned = cleanup_text(review)
    review_tokenized = tokenizer(review_cleaned)
    lemmatized_text = [lemmatizer.lemmatize(word) for word in review_tokenized]
    review_processed = vocabulary(lemmatized_text)
    if len(review_processed) < max_len:
        review_processed.extend([0] * (max_len - len(review_processed)))
    elif len(review_processed) > max_len:
        review_processed = review_processed[:max_len]
    return review_processed

def convert_to_tensor(dataframe):
    """
    Converts the dataframe values into a list of tensors and appending the sentiment for each
    review to the review tensor.

    Parameters
    ----------
    dataframe : pandas DataFrame
        Dataframe whose data to be converted.

    Returns
    -------
    combined_tensor : list[torch.tensor]
        A list of torch tensors containing the indices of each review and the sentiment 
        as the last element.
    """
    
    # Converting the dataset values to lists
    review_processed_values = dataframe['review_processed'].tolist()
    sentiment_values = dataframe['sentiment'].tolist()
    #Converting dataset values to tensors
    review_processed_tensor = torch.tensor(review_processed_values)
    sentiment_tensor = torch.tensor(sentiment_values)
    # Appending the sentiment to the review indices tensor as the last element
    sentiment_tensor = sentiment_tensor.unsqueeze(1)
    combined_tensor = torch.cat((review_processed_tensor, sentiment_tensor), dim=1)
    return combined_tensor
    

class dataset(Dataset):
    """
    Pytorch Dataset class for converting the pandas dataframes into datasets
    """
    def __init__(self,data):
        self.data = data
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, index):
        return self.data[index]
#------------------------------------------------------------------------------
# Parameter definitions

# Maximum review text sequence length
max_len = 500

# Fraction of training data of all data
train_size = 0.8
# Fraction of validation data of all data
validation_size = 0.15
# Fraction of test data of all data
test_size = 0.05

def process_data(max_len = 500, train_size = 0.8, validation_size = 0.15, test_size = 0.05):
    #------------------------------------------------------------------------------
    # Reading and transforming the dataset
    
    # Creating the necessary directories and downloading the data
    if 'data' not in os.listdir():
        os.mkdir("./data")
    
    if 'raw_data' not in os.listdir("./data"):
        os.mkdir("./data/raw_data")
    
    if "womens_clothing_ecommerce_reviews.csv" not in os.listdir("./data/raw_data"):
        subprocess.run("aws s3 cp s3://dlai-practical-data-science/data/raw/womens_clothing_ecommerce_reviews.csv ./data/raw_data",\
                       shell=True)
    
    
    # Reading the data
    data = pd.read_csv("./data/raw_data/womens_clothing_ecommerce_reviews.csv")
    # Keeping the useful columns
    data_transformed =  data[["Review Text", "Rating", "Class Name"]].copy()
    # Renaming the columns for convenience
    data_transformed.rename(columns = {"Review Text":'review', "Rating":"rating", "Class Name":"product_category"}, inplace = True)
    # dropping the rows wth empty cells 
    data_transformed.dropna(inplace = True)
    # Removing the data for product categories with less than 10 reviews
    data_transformed  = data_transformed.groupby("product_category").filter(lambda review: len(review) > 10)
    # Converting the star rating to sentiment and dropping the rating column as it is not needed anymore
    data_transformed["sentiment"] = data_transformed["rating"].apply(lambda rating: rating_to_sentiment(rating))
    data_transformed.drop(columns = "rating", inplace = True)
    # Saving the transformed dataset
    data_transformed.to_csv("./data/raw_data/womens_clothing_ecommerce_reviews_transformed.csv", index = False)
    
    
    #------------------------------------------------------------------------------
    # Balancing the dataset
    
    # Balancing the dataset based on the sentiments so we have the same number of reviews for both sentiments
    data_transformed_grouped_for_balance = data_transformed.groupby(["sentiment"])[["review","sentiment", "product_category"]]
    data_transformed_balanced = data_transformed_grouped_for_balance.apply(lambda x: \
                                    x.sample(data_transformed.groupby(["sentiment"]).size().min()))\
                                    .reset_index(drop = True)# Saving the balanced dataset
    # Saving the balanced dataset
    data_transformed_balanced.to_csv("./data/raw_data/womens_clothing_ecommerce_reviews_balanced.csv", index = False)
    
    # Creating the required directories to save the data
    if "training" not in os.listdir("./data"):
        os.mkdir("./data/training")
    
    if "validation" not in os.listdir("./data"):
        os.mkdir("./data/validation")
    
    if "test" not in os.listdir("./data"):
        os.mkdir("./data/test")
    
    # Dividing the data into train, validation and test sets
    training_data, temp_data = train_test_split(data_transformed_balanced, test_size = 1 - train_size, random_state = 5)
    validation_data, test_data = train_test_split(temp_data, test_size = test_size / validation_size, random_state = 5)
    
    # Saving the train, validation and test datasets
    training_data.to_csv("./data/training/womens_clothing_ecommerce_reviews_balanced_training.csv", index = False)
    validation_data.to_csv("./data/validation/womens_clothing_ecommerce_reviews_balanced_validation", index = False)
    test_data.to_csv("./data/test/womens_clothing_ecommerce_reviews_balanced_test", index = False)
    
    #------------------------------------------------------------------------------
    # Preprocessing the data for the NLP task
    
    # Creating a text corpus from the training and validation data
    corpus_data = pd.concat([training_data["review"], validation_data["review"]], axis = 0)
    corpus = '\n'.join(training_data["review"].values)
    
    # Saing the text corpus for future references and use
    with open("./data/corpus.txt", "w") as file:
        file.write(corpus)
    
    # Cleaning he corpus text
    corpus_cleaned = cleanup_text(corpus)
    # Creating a vocabulary from the text corpus
    vocabulary = create_vocab(corpus_cleaned, word_tokenize, WordNetLemmatizer(), "<unk>", "<pad>")
    # Saving the vocabulary for future reference and use
    torch.save(vocabulary, './models/vocabulary.pth')
    
    # Processing the reviews in the datasets and converting the review text to list of indices
    training_data["review_processed"] = training_data["review"]\
        .apply(lambda x: process_reviews(x, word_tokenize, WordNetLemmatizer(), vocabulary, max_len))
    validation_data["review_processed"] = validation_data["review"]\
        .apply(lambda x: process_reviews(x, word_tokenize, WordNetLemmatizer(), vocabulary, max_len))
    test_data["review_processed"] = test_data["review"]\
        .apply(lambda x: process_reviews(x, word_tokenize, WordNetLemmatizer(), vocabulary, max_len))
    
    # Keeping only the required columns of the datsets
    training_data_processed = training_data[["review_processed", "sentiment"]]
    validation_data_processed  = validation_data[["review_processed", "sentiment"]]
    test_data_processed  = test_data[["review_processed", "sentiment"]]
    
    # Saving the datasets for future use and reference
    training_data_processed.to_csv("./data/training/training_data_processed.csv", index = False)
    validation_data_processed.to_csv("./data/validation/validation_data_processed.csv", index = False)
    test_data_processed.to_csv("./data/test/test_data_processed.csv", index = False)
    
    # Converting the dataframe data into tensors
    training_data_tensor = convert_to_tensor(training_data_processed)
    validation_data_tensor = convert_to_tensor(validation_data_processed)
    test_data_tensor = convert_to_tensor(test_data_processed)
    
    # Creating torch Datasets
    train_dataset = dataset(training_data_tensor)
    validaton_dataset = dataset(validation_data_tensor)
    test_dataset = dataset(test_data_tensor)
    
    # Saving the torch Datasets for future sse and reference
    torch.save(train_dataset, "./data/training/training_dataset.pth")
    torch.save(validaton_dataset, "./data/validation/validation_dataset.pth")
    torch.save(test_dataset, "./data/test/test_dataset.pth")

#------------------------------------------------------------------------------
# Running the script directly
if __name__ == "__main__":
    process_data(max_len,  train_size, validation_size, test_size)
