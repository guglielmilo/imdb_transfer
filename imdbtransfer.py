#!/usr/bin/python3
import argparse
import json
import requests
import csv

def read_ratings_csv(filename):
    res = {}

    with open(filename, newline='') as csv_file:
        reader = csv.reader(csv_file, delimiter=',')
        headers = next(reader)
        try:
            for row in reader:
                res[row[0]] = int(row[1])
        except (ValueError,IndexError):
            print('Malformed {}.csv', filename)

    return res

def read_watchlist_csv(filename):
    res = []

    with open(filename, newline='') as csv_file:
        reader = csv.reader(csv_file, delimiter=',')
        headers = next(reader)
        try:
            for row in reader:
                res.append(row[1])
        except IndexError:
            print('Malformed {}.csv', filename)

    return res


class RateLimitError(Exception):
    '''from # from https://github.com/TobiasPankner/Letterboxd-to-IMDb/blob/master/letterboxd2imdb.py'''

    pass


def rate_on_imdb(imdb_id, rating, imdb_cookie):
    '''from # from https://github.com/TobiasPankner/Letterboxd-to-IMDb/blob/master/letterboxd2imdb.py'''

    req_body = {
        "query": "mutation UpdateTitleRating($rating: Int!, $titleId: ID!) { rateTitle(input: {rating: $rating, titleId: $titleId}) { rating { value __typename } __typename }}",
        "operationName": "UpdateTitleRating",
        "variables": {
            "rating": rating,
            "titleId": imdb_id
        }
    }
    headers = {
        "content-type": "application/json",
        "cookie": imdb_cookie
    }

    resp = requests.post("https://api.graphql.imdb.com/", json=req_body, headers=headers)

    if resp.status_code != 200:
        if resp.status_code == 429:
            raise RateLimitError("IMDb Rate limit exceeded")
        raise ValueError(f"Error rating on IMDb. Code: {resp.status_code}")

    json_resp = resp.json()
    if 'errors' in json_resp and len(json_resp['errors']) > 0:
        first_error_msg = json_resp['errors'][0]['message']

        if 'Authentication' in first_error_msg:
            print(f"Failed to authenticate with cookie")
            exit(1)
        else:
            raise ValueError(first_error_msg)

def add_to_imdb_watchlist(imdb_id, imdb_cookie):
    '''from # from https://github.com/TobiasPankner/Letterboxd-to-IMDb/blob/master/letterboxd2imdb.py'''

    headers = {
        "content-type": "application/json",
        "cookie": imdb_cookie
    }

    resp = requests.put(f"https://www.imdb.com/watchlist/{imdb_id}", headers=headers)

    if resp.status_code != 200:
        if resp.status_code == 429:
            raise RateLimitError("IMDb Rate limit exceeded")
        raise ValueError(f"Error adding to IMDb watchlist. Code: {resp.status_code}")

    if resp.status_code == 403:
        print(f"Failed to authenticate with cookie")
        exit(1)

def main():
    parser = argparse.ArgumentParser(description='Imports IMDb ratings and watchlist from another account')
    parser.add_argument('-c', dest='cookie', type=str, required=True, help='Cookie of the destination IMDb account')
    parser.add_argument('-r', dest='ratings', type=str, help='ratings.csv from the originating IMDb account')
    parser.add_argument('-w', dest='watchlist', type=str, help='watchlist.csv of the originating IMDb account')

    args = parser.parse_args()

    if args.ratings is None and args.watchlist is None:
        parser.error('at least one of --ratings and --watchlist is required')

    try:
        with open(args.cookie, 'r') as file:
            imdb_cookie = file.read().replace('\n', '').strip()
    except:
        print('Failed to read destination IMDb cookie file {}'.format(args.cookie))
        exit(1)

    done = {}
    done['ratings'] = []
    done['watchlist'] = []
    try:
        with open('done.json', 'r') as f:
            try:
                done = json.load(f)
            except json.decoder.JSONDecodeError as e:
                print('Already processed file broken: {}'.format(e))
    except FileNotFoundError:
        pass

    ratings = read_ratings_csv(args.ratings)

    for title in done['ratings']:
        ratings.pop(title)

    if len(ratings):
        for title, rating in ratings.items():
            try:
                rate_on_imdb(title, rating, imdb_cookie)
                done['ratings'].append(title)
                print('IMDb title {0} rated {1}'.format(title, rating))
            except RateLimitError:
                print('IMDb rate limit exceeded, try again in a few minutes')
                break
            except Exception as e:
                print(e)
                return

        with open('done.json', 'w+') as f:
            json.dump(done, f)
            print('Processed titles ratings saved in {}'.format((f.name)))

    watchlist = read_watchlist_csv(args.watchlist)

    for title in done['watchlist']:
        watchlist.remove(title)

    if len(watchlist):
        for title in watchlist:
            try:
                add_to_imdb_watchlist(title, imdb_cookie)
                done['watchlist'].append(title)
                print('IMDb title {0} added to the watchlist'.format(title))
            except RateLimitError:
                print('IMDb rate limit exceeded, try again in a few minutes')
                raise
            except Exception as e:
                print(e)
                return

        with open('done.json', 'w+') as f:
            json.dump(done, f)
            print('Processed watchlist titles saved in {}'.format((f.name)))

if __name__ == '__main__':
    main()
