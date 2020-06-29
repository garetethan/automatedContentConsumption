'''
# Automated Content Consumption
A lightweight feed aggregator that supports manual creation of backlogs.
## `info.txt` format
### Downloaded and linked streams
stream type
RSS feed url (optional)
current item date (yyyy-mm-dd format)
current item name
current item file extension or current url     # If this is the current extension, it should *not* include the period at the beginning of the extension.
current item progress
                                               # This line is intentionally left blank so that when the file is read with readlines(), the last character of every line is `\n`.
### Manual streams
type
current item date (yyyy-mm-dd format)
current item name
current item progress
                                               # This line is intentionally left blank so that when the file is read with readlines(), the last character of every line is `\n`.
## `queue.txt` format
yyyy-mm-dd;first item name with semicolons removed / replaced;first item url
yyyy-mm-dd;second item name;second item url
[...]
'''

import enum
# RSS metadata downloading.
import feedparser
# Used to get the contents of directories, and determine whether something is a file or a directory.
import os
import re
import shutil
# Used to tell the OS to open media files.
import subprocess
# Just for sys.stderr
import sys
# All the graphics.
import tkinter as tk
# File downloading.
import urllib.request
# Used to tell the OS to open webpages.
import webbrowser

# When downloading using RSS, a downloaded stream will stop downloading when this many items are saved locally. (Prevents using too much disk space.)
# Once this limit is reached, old files (that have been consumed) must be manually deleted.
ITEM_LIMIT = 10 ** 6

# Name of directory containing all content data.
CATEGORY_DIR = 'categories'

# Name of memo file (where memo box data is stored).
MEMO_PATH = 'memo.txt'

# The string used to separate the date, name, and (when applicable) URL of an item in a queue.
SEP = ';'

# Replace all non-ASCII characters in item names with underscores when saving new items. This helps prevent encoding issues.
FORCE_ASCII = False

# Only dates strictly after the BEGINNING_OF_TIME and strictly before the END_OF_TIME are supported.
BEGINNING_OF_TIME = '1000-01-01'
END_OF_TIME = '9000-01-01'

CATEGORY_WIDTH = 200
POPUP_WIDTH = 500

# Font defaults.
DEFAULT_FONT = ('Helvetica', 12)
HEADER_FONT = ('Courier', 20)

# Default padding for, like, everything.
PADX = 6
PADY = 6

# Default tk.Button wraplength value.
BUTTON_WRAP_LEN = 200

class StreamType(enum.Enum):
	DOWNLOADED = 'downloaded'
	LINKED = 'linked'
	MANUAL = 'manual'
	
	# Allow comparison with strs read from files.
	def __eq__(self, other):
		if isinstance(other, StreamType):
			return self.value == other.value
		else:
			return self.value == other

def main():
	root = tk.Tk()
	app = MainMenu(root)
	root.title('Automated Content Consumption')
	root.mainloop()

class MainMenu(tk.Frame):
	'''Display the main menu. Let the user open (where possible) or complete the current item from any existing category.'''
	def __init__(self, master):
		super().__init__(master)
		self.master = master

		# If the main content directory has not been created yet, treat as first run.
		try:
			os.mkdir(CATEGORY_DIR)
			self.intro()
		except FileExistsError:
			pass
		self.displayCategories()
		self.displayButtons()
		self.displayMemoBox()

	def intro(self):
		'''Display introductory message.'''
		win = tk.Toplevel(self.master)
		win.title('Introduction')
		with open('README.md') as introFile:
			intro = 'Hey, it looks like you might be new here. If so, let me explain how this works.\n' + introFile.read()
		# A monospace font is used to display the info / queue file formatting correctly.
		introText = tk.Text(win, bg=win.cget('bg'), bd=0, font=('Courier', DEFAULT_FONT[1]), width=100, wrap='word')
		introText.insert('end', intro)
		introText.tag_add('centered', '1.0', 'end')
		introText.tag_config('centered', justify='left')
		# Makes the text uneditable.
		introText.config(state='disabled')
		display(introText, row=0, column=0)
		scroller = tk.Scrollbar(win, command=introText.yview)
		display(scroller, row=0, column=1, sticky='ns')
		introText.config(yscrollcommand=scroller.set)
		closeButton = displayButton(win, text='Close', command=win.destroy, columnspan=2)

	def displayCategories(self):
		'''Find and draw all existing content categories.'''
		categoryNames = [entry for entry in sorted(os.listdir(CATEGORY_DIR)) if os.path.isdir(f'{CATEGORY_DIR}/{entry}')]
		self.categories = []
		# First column is reserved for buttons.
		column = 1
		for categoryName in categoryNames:			
			# Categories display themselves when they are created.
			category = Category(self.master, categoryName, column)
			self.categories.append(category)
			column += 1

	def displayButtons(self):
		'''Draw other buttons.'''
		# Button text and command components (the only things that vary).
		buttonParts = [('Update all streams that have RSS feeds', self.updateRSS),
			('Add new category', self.addCategory),
			('Edit existing category', self.editCategory),
			('Add new stream', self.addStream),
			('Edit existing stream', self.editStream),
			('Refresh', self.refresh),
			('Quit', self.master.quit)
		]
		for i in range(len(buttonParts)):
			displayButton(self.master, text=buttonParts[i][0], command=buttonParts[i][1], row=i, column=0)

	def updateRSS(self):
		'''Update all streams that have RSS feeds. Core updating code is in Stream.updateRSS().'''
		win = tk.Toplevel(self.master)
		win.title('Updating streams')
		displayMessage(win, text='Updating RSS feeds (for all streams that have a defined RSS feed) in all categories. This is likely to take a while if any of these streams are downloaded. Because of the (single-threaded) nature of Python, your OS will probably tell you that this program is not responding. It is probably fine and not stuck, but just working hard.', width=POPUP_WIDTH)
		displayMessage(win, text='If you need to stop in the middle of updating, you will likely stop in the middle of downloading a file (assuming you have at least one downloaded stream). If you pay attention to what stream is updating when you stop, then you can close this window (which halts updating) and then manually delete the last media file in that stream (which will only be partially downloaded). This will put things in a clean, stable state so that you can continue updating later.', width=POPUP_WIDTH)
		streamMessage = displayMessage(win, text='', width=POPUP_WIDTH, row=2)
		progressMessage = displayMessage(win, text='', width=POPUP_WIDTH, row=3)
		for category in self.categories:
			category.updateRSS(self.master, streamMessage, progressMessage)
		win.destroy()
		self.refresh()

	def addCategory(self):
		'''Open a window to let the user specify values to create a new category, and create it.'''
		win = tk.Toplevel(self.master)
		win.title('Create a new category')
		nameVar = requestText(win, description='Enter the name of the new category below.')
		def submit():
			name = nameVar.get()
			if not os.path.isdir(f'{CATEGORY_DIR}/{name}'):
				os.mkdir(f'{CATEGORY_DIR}/{name}')
			self.refresh()
			win.destroy()
		displayButton(win, text='Submit', command=submit)

	def editCategory(self):
		'''Open a window to let the user specify modifications to an existing category, and modify it.'''
		win = tk.Toplevel(self.master)
		win.title('Edit category')
		explanation = displayMessage(win, text=f'The only thing that you can change about a category is its name. If you want to change what streams are in a category, or properties of those streams, use the button to edit streams. If you want to delete a category, you can do so by removing the directory (folder) from the "{CATEGORY_DIR}" directory. You will have to refresh after doing this to see your changes take effect.', width=POPUP_WIDTH)
		oldNameVar = requestSelection(win, description='Which category do you want to rename?', options=[category.name for category in self.categories])
		newNameVar = requestText(win, description='What do you want to change it to?')
		def submit():
			oldName = oldNameVar.get()
			newName = newNameVar.get()
			os.rename(f'{CATEGORY_DIR}/{oldName}', f'{CATEGORY_DIR}/{newName}')
			category = next(c for c in self.categories if c.name == oldName)
			category.name = newName
			self.refresh()
			win.destroy()
		submitButton = displayButton(win, text='Submit', command=submit)

	def addStream(self):
		'''Open a window to let the user specify values to create a new content stream, and create it.'''
		win = tk.Toplevel(self.master)
		win.title('Add new stream')
		typeVar = requestSelection(win, 'Type of new stream:', tuple(type_.value for type_ in StreamType))
		displayButton(win, text='Remind me what the different types are', command=self.intro)
		nameVar = requestText(win, 'Name of new stream:')
		categoryVar = requestSelection(win, 'Category to add to:', [category.name for category in self.categories])
		rssVar = requestText(win, 'RSS feed (optional and only for downloaded or linked streams):')
		def submit():
			streamType = typeVar.get()
			name = nameVar.get()
			categoryName = categoryVar.get()
			rss = rssVar.get()
			streamPath = f'{CATEGORY_DIR}/{categoryName}/{name}'
			try:
				os.mkdir(streamPath)
			except FileExistsError:
				pass
			if streamType == StreamType.MANUAL:
				infoLines = (streamType, BEGINNING_OF_TIME, '', '')
			# Downloaded or linked.
			else:
				infoLines = (streamType, rss, BEGINNING_OF_TIME, '', '', '')
			try:
				with open(streamPath + '/info.txt', 'x') as infoFile:
					infoFile.writelines(line + '\n' for line in infoLines)
			except FileExistsError:
				pass
			if streamType == StreamType.LINKED:
				# Create the queue file if it does not exist yet.
				try:
					open(streamPath + '/queue.txt', 'x').close()
				except FileExistsError:
					pass
			category = next(c for c in self.categories if c.name == categoryName)
			newStream = Stream(category.name, name)
			# Remove old category info (so that it doesn't appear in the background).
			category.grid_forget()
			category.streams.add(newStream)
			category.draw()
			win.destroy()
		submitButton = displayButton(win, text='Submit', command=submit)

	def editStream(self):
		'''Open a window that lets the user specify modifications to be made to an existing stream, and make them.'''
		# The first window is just to get the category which the stream to be edited is in. This saves us from having to create a list of all streams in all categories (and then re-finding the chosen stream).
		categoryWin = tk.Toplevel(self.master)
		categoryWin.title = ('Edit a stream')
		displayMessage(categoryWin, 'It is not possible to change the type of a stream. If you want to do this, you will have to delete this stream and make a new one of a different type.', width=POPUP_WIDTH)
		oldCategoryVar = requestSelection(categoryWin, description='What category is the stream that you want to change in?', options=[category.name for category in self.categories if category.streams])
		def proceed():
			oldCategoryName = oldCategoryVar.get()
			oldCategory = next(c for c in self.categories if c.name == oldCategoryName)
			categoryWin.destroy()
			# We have to "embed" the second window inside the 'proceed' command of the first so that the second doesn't open before the button is clicked.
			mainWin = tk.Toplevel(self.master)
			main.title = ('Edit a stream')
			oldStreamVar = requestSelection(mainWin, description='What stream do you want to edit?', options=[stream.name for stream in oldCategory.streams])
			newCategoryVar = requestSelection(mainWin, description='If you want to move it to a different category, choose which below.', options=[category.name for category in self.categories], defaultValue=oldCategoryName)
			newStreamVar = requestText(mainWin, description='If you want to rename it, enter the new name below. (Otherwise, leave it blank.)')
			rssVar = requestText(mainWin, description='If you want to change the RSS feed, enter the new one below. (Otherwise, leave it blank.)')
			def submit():
				# Gather data.
				newCategoryName = newCategoryVar.get()
				newCategory = next(category for category in self.categories if category.name == newCategoryName)
				oldStreamName = oldStreamVar.get()
				stream = next(stream for stream in oldCategory.streams if stream.name == oldStreamName)
				oldCategory.streams.remove(stream)
				newStreamName = newStreamVar.get() or oldStreamName
				# Move stream directory.
				newStreamPath = f'{CATEGORY_DIR}/{newCategoryName}/{newStreamName}'
				os.rename(f'{CATEGORY_DIR}/{oldCategoryName}/{oldStreamName}', newStreamPath)
				# Update RSS.
				if self.type != StreamType.MANUAL:
					newRSS = rssVar.get()
					if newRSS:
						stream.rss = newRSS
						overwriteLinesInFile(newStreamPath + '/info.txt', {1: newRSS})
				# Move stream object into new category's list and rename stream object.
				newCategory.streams.add(stream)
				stream.name = newStreamName
				self.refresh()
				mainWin.destroy()
			displayButton(mainWin, 'Submit', command=submit)
		displayButton(categoryWin, 'Proceed', command=proceed)

	def refresh(self):
		'''Refresh categories so that the user can see their changes. Do not touch the memo box.'''
		for category in self.categories:
			category.grid_forget()
		self.displayCategories()
		self.master.update()
		self.master.update_idletasks()

	def displayMemoBox(self):
		'''Display a text entry with a button to save so that the user can save notes for their future selves.'''
		memoBox = tk.Text(self.master, width=50, height=2, wrap='word', font=DEFAULT_FONT)
		display(memoBox, row=12, column=0, columnspan=len(self.categories) + 1)
		try:
			with open(MEMO_PATH) as memoFile:
				memoContent = memoFile.read()
			memoBox.insert('1.0', memoContent)
		except FileNotFoundError:
			open(MEMO_PATH, 'x').close()
		def saveMemo():
			memoContent = memoBox.get('1.0', 'end-1c')
			with open(MEMO_PATH, 'w') as memoFile:
				memoFile.write(memoContent)
		displayButton(self.master, text='Save memo', command=saveMemo, row=13, columnspan=len(self.categories) + 1)

class Stream():
	'''Represent one stream of content, like a podcast or a YouTube channel.'''
	def __init__(self, categoryName, streamName):
		self.name = streamName
		self.categoryName = categoryName
		self.path = f'{CATEGORY_DIR}/{self.categoryName}/{self.name}'

		# Read stream details.
		with open(self.path + '/info.txt') as infoFile:
			# Save lines but chop newlines off the end of each line.
			infoLines = tuple(line[:-1] for line in infoFile.readlines())
		self.type = infoLines[0]
		if self.type == StreamType.MANUAL:
			self.currentDate, self.currentName, self.currentProgress = infoLines[1:4]
		# Downloaded or linked.
		else:
			self.rss = infoLines[1] if infoLines[1] else None
			self.currentDate = infoLines[2]
			self.currentName = infoLines[3]
			if self.type == StreamType.DOWNLOADED:
				self.currentExtension = infoLines[4]
			# Linked.
			else:
				self.currentUrl = infoLines[4]
			self.currentProgress = infoLines[5]

	def updateRSS(self, master, progressMessage):
		'''Get the RSS feed for this stream and download all new listed items (up to ITEM_LIMIT).'''
		if self.type != StreamType.MANUAL and self.rss:
			entries = sorted(feedparser.parse(self.rss)['entries'], key=self.parseDate)
			i = len(entries) - 1
			if self.type == StreamType.DOWNLOADED:
				alreadyDownloaded = sorted([entry for entry in os.listdir(self.path) if os.path.isfile(f'{self.path}/{entry}') and entry != 'info.txt'])
				# Date (str) of the latest item already downloaded.
				latestDownloaded = alreadyDownloaded[-1].split(SEP, maxsplit=1)[0] if alreadyDownloaded else BEGINNING_OF_TIME
				while i > 0 and self.parseDate(entries[i]) > latestDownloaded:
					i -= 1
				i += 1

				# If this stream has been disabled but there are updates now, enable it.
				if self.currentDate == END_OF_TIME and i < len(entries) - 1:
					overwriteLinesInFile(self.path + '/info.txt', {2: self.parseDate(entries[i]), 3: self.parseName(entries[i]), 4: self.parseUrlAndExtension(entries[i])[1]})

				end = max(ITEM_LIMIT - len(alreadyDownloaded) + i, 0)
				for j, entry in enumerate(entries[i:end]):
					name = self.parseName(entry)
					downloadUrl, extension = self.parseUrlAndExtension(entry)
					forceUpdateMessage(master, progressMessage, f'Downloading \'{name}\' ({j + 1} / {end - i}).')
					with urllib.request.urlopen(downloadUrl) as response, open(f'{self.path}/{self.parseDate(entry)}{SEP}{name}.{extension}', 'xb') as outFile:
						shutil.copyfileobj(response, outFile)

			# Type is linked.
			else:
				# Downloading metadata is fast enough that there is no point trying to update for every item.
				with open(self.path + '/queue.txt') as queueFile:
					queueLines = queueFile.readlines()
					latestSaved = queueLines[-1].split(SEP, maxsplit=1)[0] if queueLines else BEGINNING_OF_TIME

				while i > 0 and self.parseDate(entries[i]) > latestSaved:
					i -= 1
				i += 1

				# If this stream has been disabled but there are updates now, enable it.
				if self.currentDate == END_OF_TIME and i < len(entries) - 1:
					overwriteLinesInFile(self.path + '/info.txt', {2: self.parseDate(entries[i]), 3: self.parseName(entries[i]), 4: entries[i].link})

				newItems = [f'{self.parseDate(entry)}{SEP}{self.parseName(entry)}{SEP}{entry.link}\n' for entry in entries[i:]]

				with open(self.path + '/queue.txt', 'a', errors='replace') as queueFile:
					queueFile.writelines(newItems)

	def parseDate(self, entry):
		for key in ['published_parsed', 'updated_parsed']:
			try:
				pubParsed = entry[key]
			except KeyError:
				continue
			return f'{pubParsed[0]}-{pubParsed[1]:02}-{pubParsed[2]:02}'
		raise LookupError(f'Stream {self.categoryName}/{self.name}: Failed to find the date for an entry.')

	def parseName(self, entry):
		if self.type == StreamType.DOWNLOADED:
			# If on Windows, also exclude chars forbidden from Windows file names.
			if os.name == 'nt':
				# Source: https://stackoverflow.com/a/31976060
				pattern = f'[{SEP}<>:"/\\|?*]'
			# Assume os.name == 'posix'.
			else:
				pattern = f'[{SEP}/]'
		# Linked.
		else:
			pattern = SEP
		if FORCE_ASCII:
			pattern += r'|[^\x00-\x7F]'
		return re.sub(pattern, '_', entry.title)

	def parseUrlAndExtension(self, entry):
		'''Finds and parses tne download URL and extension of an entry. Only for downloaded streams.'''
		try:
			downloadUrl = next(link.href for link in entry.links if link.rel == 'enclosure')
		except StopIteration:
			raise LookupError(f'Stream {self.categoryName}/{self.name}: My method for finding the link to download media files has failed for the item \'{entry.title}\'.')
		match = re.search(r'\.(\w+)([?#].*)?$', downloadUrl)
		if match:
			return (downloadUrl, match[1])
		else:
			raise ValueError(f'Stream {self.categoryName}/{self.name}: Unable to extract the file extension for \'{entry.title}\' from <{downloadUrl}>.')

	def __repr__(self):
		return f'Stream({self.categoryName}, {self.name})'

	def __str__(self):
		return f'Stream \'{self.name}\' in category \'{self.categoryName}\''
	
	def __lt__(self, other):
		return self.currentDate < other.currentDate

	def __gt__(self, other):
		return self.currentDate > other.currentDate

class Category(tk.Frame):
	'''Represent a category of streams like 'Videos' or 'Favourites'. May contain multiple streams of different types.'''
	def __init__(self, master=None, name=None, column=0):
		super().__init__(master)
		self.name = name
		self.path = f'{CATEGORY_DIR}/{self.name}'
		self.streams = set(Stream(self.name, streamName) for streamName in os.listdir(self.path) if os.path.isdir(f'{self.path}/{streamName}'))
		self.currentStream = min(self.streams) if self.streams else None
		self.column = column
		self.draw()

	def completeCurrent(self):
		'''Advance the current stream by one item.'''
		# Get item list.
		if self.currentStream.type == StreamType.DOWNLOADED:
			itemList = [entry for entry in sorted(os.listdir(self.currentStream.path)) if os.path.isfile(f'{self.currentStream.path}/{entry}') and entry != 'info.txt']
		# linked or manual.
		else:
			with open(self.currentStream.path + '/queue.txt') as queueFile:
				# Last char of each line is '\n'.
				itemList = [line[:-1] for line in queueFile.readlines()]

		# If there is no current.
		if not self.currentStream.currentDate or self.currentStream.currentDate == BEGINNING_OF_TIME:
			# Does not represent the last item in the list, but that the index of the "next" item is 0.
			oldIndex = -1
		# If the stream has been paused.
		elif self.currentStream.currentDate == END_OF_TIME:
			oldIndex = len(itemList) - 1
		# For any stream type.
		else:
			oldIndex = next(i for i, item in enumerate(itemList) if item.startswith(f'{self.currentStream.currentDate}{SEP}{self.currentStream.currentName}'))

		# If current is last available.
		if oldIndex + 1 >= len(itemList):
			win = tk.Toplevel()
			win.title('End of stream')
			displayMessage(win, text='You have reached the end of this stream (until it is updated).', width=POPUP_WIDTH)
			displayButton(win, text='Close', command=win.destroy)
			# We need to temporarily disable this stream so that any other streams that still have next items can be displayed.
			self.currentStream.currentDate = END_OF_TIME
		# There is a next one.
		else:
			# Update stream object.
			if self.currentStream.type == StreamType.DOWNLOADED:
				currentInfo, self.currentStream.currentExtension = itemList[oldIndex + 1].rsplit('.', maxsplit=1)
				self.currentStream.currentDate, self.currentStream.currentName = currentInfo.split(SEP, maxsplit=1)
			elif self.currentStream.type == StreamType.LINKED:
				self.currentStream.currentDate, self.currentStream.currentName, self.currentStream.currentUrl = itemList[oldIndex + 1].split(SEP, maxsplit=2)
			# manual.
			else:
				self.currentStream.currentDate, self.currentStream.currentName = itemList[oldIndex + 1].split(SEP, maxsplit=2)
		self.currentStream.currentProgress = '0'

		# Update current in info file.
		infoLines = [self.currentStream.type]
		if self.currentStream.type != StreamType.MANUAL:
			infoLines.append(self.currentStream.rss if self.currentStream.rss else '')
		infoLines.append(self.currentStream.currentDate)
		infoLines.append(self.currentStream.currentName)
		if self.currentStream.type == StreamType.DOWNLOADED:
			infoLines.append(self.currentStream.currentExtension)
		elif self.currentStream.type == StreamType.LINKED:
			infoLines.append(self.currentStream.currentUrl)
		infoLines.append(self.currentStream.currentProgress)
		infoLines.append('')

		with open(self.currentStream.path + '/info.txt', 'w') as infoFile:
			infoFile.writelines(line + '\n' for line in infoLines)

		# Update UI.
		self.grid_forget()
		self.draw()

	def draw(self):
		'''Draw all of the parts of this category. Not to be confused with display(), which is defined below and works on tkinter elements.'''
		# Category extends tk.Frame.
		display(self, row=0, column=self.column, rowspan=8)
		# Keep track of what rows have already been used. Putting every element in the first available row (regardless of what the type of the current stream is) means that manual streams will appear shorter than downloaded and linked, and the buttons that all streams have (eg "Open directory") will appear in different rows for different categories. But some users might only use manual streams, and some only downloaded and linked.
		rowIndex = 0
		displayMessage(self.master, text=self.name, width=CATEGORY_WIDTH, font=HEADER_FONT, row=rowIndex, column=self.column)
		rowIndex += 1
		if self.streams:
			self.currentStream = self.currentStream
			displayMessage(self.master, text=self.currentStream.name, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
			rowIndex += 1
			if self.currentStream.type == StreamType.MANUAL:
				for text in (self.currentStream.currentName, self.currentStream.currentDate):
					displayMessage(self.master, text=text, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
					rowIndex += 1

			# Downloaded or linked.
			else:
				if self.currentStream.currentName:
					displayMessage(self.master, text=self.currentStream.currentName, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
				else:
					displayMessage(self.master, text='Click \'Current\' to advance to first item', width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
				rowIndex += 1
				displayMessage(self.master, text=self.currentStream.currentDate, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
				rowIndex += 1

			# Progress displaying and saving. Here there is a difference between '' and None.
			self.currentProgressMessage = displayMessage(self.master, text=self.currentStream.currentProgress, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
			rowIndex += 1
			self.progressEntry = tk.Entry(self.master, width=8, font=DEFAULT_FONT)
			display(self.progressEntry, row=rowIndex, column=self.column)
			rowIndex += 1
			def saveProgress():
				progress = self.progressEntry.get()
				overwriteLinesInFile(self.currentStream.path + '/info.txt', {3 if self.currentStream.type == StreamType.MANUAL else 5: progress})
				# Make update visible to user.
				self.currentProgressMessage.configure(text=progress)
			displayButton(self.master, text='Save progress', command=saveProgress, row=rowIndex, column=self.column)
			rowIndex += 1

			if self.currentStream.type != StreamType.MANUAL:
				def openCurrent():
					if self.currentStream.currentDate == BEGINNING_OF_TIME:
						win = tk.Toplevel()
						win.title('Empty stream')
						displayMessage(win, text='This stream does not yet contain any media items to open.', width=POPUP_WIDTH)
						displayButton(win, text='Close', command=win.destroy)
					else:
						if self.currentStream.type == StreamType.DOWNLOADED:
							openMedia(f'{self.currentStream.path}/{self.currentStream.currentDate}{SEP}{self.currentStream.currentName}.{self.currentStream.currentExtension}')
						# Linked.
						else:
							openMedia(self.currentStream.currentUrl)
				displayButton(self.master, text='Open', command=openCurrent, row=rowIndex, column=self.column)
				rowIndex += 1

			displayButton(self.master, text='Complete', command=self.completeCurrent, row=rowIndex, column=self.column)
			rowIndex += 1
			def openInfoFile():
				openMedia(self.currentStream.path + '/info.txt')
			displayButton(self.master, text='Open info file', command=openInfoFile, row=rowIndex, column=self.column)
			rowIndex += 1

		# We have no streams.
		else:
			displayMessage(self.master, text='This category does not contain any streams.', width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
			rowIndex += 1

	def updateRSS(self, master, streamMessage, progressMessage):
		for stream in self.streams:
			forceUpdateMessage(self.master, streamMessage, f'Updating {self.name}/{stream.name}.')
			stream.updateRSS(master, progressMessage)

	def __repr__(self):
		return f'Category({self.master}, {self.name})'

	def __str__(self):
		return f'Category \'{self.name}\' with {len(self.streams)} streams'

def display(widget, *args, **kwargs):
	'''Wrap .grid() to automatically apply padding.'''
	widget.grid(*args, **kwargs, padx=PADX, pady=PADY)

def displayMessage(master, text, width, font=DEFAULT_FONT, *args, **kwargs):
	'''Create and display a message.'''
	message = tk.Message(master, text=text, width=width, font=font, justify='center')
	display(message, *args, **kwargs)
	return message

def forceUpdateMessage(master, message, text, *args, **kwargs):
	'''An attempt to *really* make tkinter remove the old text of a message and display new text.'''
	gridInfo = message.grid_info()
	message.grid_forget()
	message.configure(text=text)
	display(message, row=gridInfo['row'], column=gridInfo['column'], *args, **kwargs)
	master.update()
	master.update_idletasks()

def displayButton(master, text, command, wraplength=BUTTON_WRAP_LEN, *args, **kwargs):
	'''Create and display a button.'''
	button = tk.Button(master, text=text, command=command, wraplength=wraplength, font=DEFAULT_FONT)
	display(button, *args, **kwargs)
	return button

def requestText(win, description=None, width=POPUP_WIDTH):
	'''Create a Message and an Entry that prompt the user for some text. Return the entry object (so that the caller can use .get() on it to get the submitted value.'''
	if description:
		displayMessage(win, text=description, width=width)
	entry = tk.Entry(win, width=32, font=DEFAULT_FONT)
	display(entry)
	return entry

def requestSelection(win, description=None, options=None, defaultValue=None, width=POPUP_WIDTH):
	'''Create a drop-down menu, usually with a message above it, letting the user choose one. options is required, even though it has a default value.'''
	if not options:
		raise ValueError('Options must be a non-empty list.')
	if description:
		displayMessage(win, text=description, width=width)
	choiceVar = tk.StringVar(win)
	if not defaultValue:
		defaultValue = options[0]
	choiceVar.set(defaultValue)
	menu = tk.OptionMenu(win, choiceVar, *options)
	display(menu)
	return choiceVar

def openMedia(filepath):
	'''Tells the OS to open the file at filepath in the default program, or the web page at filepath (a web address) in the default browser.'''
	if filepath.startswith('http'):
		webbrowser.open(filepath)
	else:
		if os.name == 'nt':
			os.startfile(filepath)
		# Assume os.name == 'posix'
		else:
			subprocess.run(['xdg-open', filepath], stdout=subprocess.DEVNULL, check=True)

def overwriteLinesInFile(filepath, replacements):
	'''replacements (dict): Maps *zero-indexed* line numbers to the strs (exluding newlines) that should overwrite the old lines.'''
	with open(filepath) as fileHandle:
		lines = fileHandle.readlines()
	for index, newLine in replacements.items():
		lines[index] = newLine + '\n'
	with open(filepath, 'w') as fileHandle:
		fileHandle.writelines(lines)

if __name__ == '__main__':
	main()
