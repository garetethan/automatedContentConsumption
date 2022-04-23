# Automated Content Consumption
## Description
Automated Content Consumption is designed to keep track of all of the different streams of media that you want to enjoy. Podcasts, YouTube channels, web comics, blogs, and even books. It is based strongly on the idea that media should be consumed chronologically.

## Dependencies
AutoConCon is written in Python 3 and uses Feedreader (`pip install feedreader`) to download data from RSS feeds and tkinter (part of the Python Standard Library) for graphics.

## Definitions
A media item is one piece of content, equivalent to one file. This could be a podcast episode, a YouTube video, or an online article. Every media item has a date associated with it (usually the day that it was published). Streams contain media items. A stream might be a particular blog, podcast, or YouTube channel. Categories contain streams. A category might be called something like "YouTube videos" or "Urgent". If you are just starting, you should create a category first, then put one or more streams in that category.

Categories are directories (folders) inside of the main content directory (defined as `CATEGORY_DIR` in `autoConCon.py`). Streams are directories inside of categories. Every stream directory should have an `info.txt` file in it (created for you if you use the button to add a new stream), containing the type of the stream, the RSS feed for the stream (if it has one), and details about the media item that is at the front of the stream's queue.

### Streams
There are three types of streams: downloaded, linked, and manual.

#### Downloaded
A downloaded stream is a list of locally saved files that this program goes through in order, from oldest to newest. The names of these files are assumed to have a particular format that includes the date that they were created / released on. A downloaded stream can connect to an RSS feed to download new files for you. Opening an item in a downloaded stream will tell the OS to open the file in whatever the default program is for that filetype. Completing an item in a downloaded stream does not delete the file; this must be done manually. The growth of a downloaded stream caused by RSS updating can be limited to a certain number of items by setting `ITEM_LIMIT` in `autoConCon.py`, which has a default value of one million.

#### Linked
A linked stream does not store any media data locally. Instead, it is a list of item names and URLs that are saved in the `queue.txt` files in its directory. It can still have an RSS feed to retrieve new URLs. Opening an item in a linked stream will open the URL in the default web browser.

#### Manual
A manual stream is what you should use for media items that are not files that you can access nor URLs, but physical objects like books. If you want to add new items to a manual stream's queue, you have to edit its `queue.txt` file manually. It will still have a `Complete` button that can be used to move on to the next item. Manual streams do not support RSS functionality.

## Creating backlogs
If you want to manually add items to a downloaded feed (such as those that may be too old to be on an RSS feed any more), just download them in the stream directory and follow the naming convention (`yyyy-mm-dd;item name.filetype`). Note that files with dates older than that of the current item in the stream will be ignored by the program (as it progresses strictly chronologically).

For linked and manual streams, just add the date, name, and URL of each item to the queue.txt file (`yyyy-mm-dd;item name;url`), putting one item on each line. Note that these files are never sorted by the program, so you can add items wherever you want and the program will respect the order that you use (even if they are not in chronological order). For linked streams, however, the item at the bottom of the queue file will determine which items are added to the queue.

## Design
I have purposefully designed AutoConCon so that it is easy to see how it works and mess with it. The Python file that runs everything (`autoConCon.py`) is under seven hundred lines and has several customizable global variables at the top, so hopefully it is easy to understand and navigate should you want to change something. The simplicity of the `info.txt` files means that you can change the current item in a stream or the RSS feed of a stream manually (without launching the program).

## Technical details
### `info.txt` examples
Note that comments cannot actually be included in the info files as shown.
#### Downloaded
```
downloaded
http://nodumbqs.libsyn.com/rss      # RSS feed (may be a blank line).
2019-11-30                          # Date of publication of current item.
072 - How Did Humans Find Hawaii?   # Name of current item.
mp3                                 # File extension of the current item. Should *not* include the period at the beginning of the extension.
0:00                                # Your progress through the current item (any string).
                                    # This line is intentionally left blank so that when the file is read with readlines(), the last character of every line is a newline.
```

#### Linked
```
linked
https://www.youtube.com/feeds/videos.xml?channel_id=UCyNdC48md19x0thA_rv2a8g   # RSS feed (may be a blank line).
2016-11-30                                                                     # Date of publication of current item.
I Do (original song)                                                           # Name of current item.
https://www.youtube.com/watch?v=EoSqKWr3nnc                                    # URL of current item.
0:00                                                                           # Your progress through the current item (any string).
                                                                               # Intentional blank line.
```

#### Manual
```
manual
1950-10-16                             # Current item date.
The Lion, the Witch and the Wardrobe   # Current item name.
p 31                                   # Current item progress.
                                       # Intentional blank line.
```

### `queue.txt` format
#### Linked
```
yyyy-mm-dd;first item name with semicolons removed / replaced;first item url
yyyy-mm-dd;second item name;second item url
[...]
```
#### Manual
```
yyyy-mm-dd;first item name with semicolons removed / replaced
yyyy-mm-dd;second item name
[...]
```
