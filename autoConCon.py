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
ITEM_LIMIT = 1000000

# Name of directory containing all content data.
CATEGORY_DIR = 'categories'

# Name of memo file (where memo box data is stored).
MEMO_PATH = 'memo.txt'

# The string used to separate the date, name, and (when applicable) URL of an item in a queue.
SEP = ';'

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
			category = ContentCategory(self.master, categoryName, column)
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
		'''Update all RSS feeds by downloading all new files.'''
		win = tk.Toplevel(self.master)
		win.title('Updating streams')
		displayMessage(win, text='Updating RSS feeds (for all streams that have a defined RSS feed) in all categories. This is likely to take a while if any of these streams are downloaded. Because of the (single-threaded) nature of Python, your OS will probably tell you that this program is not responding. It is probably fine and not stuck, but just working hard.', width=POPUP_WIDTH)
		displayMessage(win, text='If you need to stop in the middle of updating, you will likely stop in the middle of downloading a file (assuming you have at least one downloaded stream). If you pay attention to what stream is updating when you stop, then you can close this window (which halts updating) and then manually delete the last media file in that stream (which will only be partially downloaded). This will put things in a clean, stable state so that you can continue updating later.', width=POPUP_WIDTH)
		streamMessage = displayMessage(win, text='', width=POPUP_WIDTH, row=2)
		progressMessage = displayMessage(win, text='', width=POPUP_WIDTH, row=3)
		for category in self.categories:
			for stream in category.streams:
				forceUpdateMessage(self.master, streamMessage, f'Updating {category.name}/{stream.name}.')
				stream.updateRSS(self.master, progressMessage)
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
		typeVar = requestSelection(win, 'Type of new stream:', STREAM_TYPES)
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
			newStream = ContentStream(category.name, name)
			# Remove old category info (so that it doesn't appear in the background).
			category.grid_forget()
			category.streams.append(newStream)
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
				oldStreamIndex, oldStream = next((i, stream) for (i, stream) in enumerate(oldCategory.streams) if stream.name == oldStreamName)
				newStreamName = newStreamVar.get() or oldStreamName
				newRss = rssVar.get()
				# Move stream directory.
				newStreamPath = f'{CATEGORY_DIR}/{newCategoryName}/{newStreamName}'
				os.rename(f'{CATEGORY_DIR}/{oldCategoryName}/{oldStreamName}', newStreamPath)
				# Update RSS.
				if newRss and oldStream.type != StreamType.MANUAL:
					oldStream.rss = newRss
					overwriteLineInFile(newStreamPath + '/info.txt', 1, newRss + '\n')
				# Move stream obect into new category's list and rename stream object.
				newCategory.streams.append(oldCategory.streams.pop(oldStreamIndex))
				oldStream.name = newStreamName
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
		if os.path.isfile(MEMO_PATH):
			with open(MEMO_PATH) as memoFile:
				memoContent = memoFile.read()
			memoBox.insert('1.0', memoContent)
		# Memo file does not exist.
		else:
			open(MEMO_PATH, 'w').close()
		def saveMemo():
			memoContent = memoBox.get('1.0', 'end-1c')
			with open(MEMO_PATH, 'w') as memoFile:
				memoFile.write(memoContent)
		displayButton(self.master, text='Save memo', command=saveMemo, row=13, columnspan=len(self.categories) + 1)

class ContentStream():
	'''Represent one stream of content, like a podcast or a YouTube channel.'''
	def __init__(self, categoryName, streamName):
		self.name = streamName
		self.categoryName = categoryName

		streamPath = f'{CATEGORY_DIR}/{self.categoryName}/{self.name}'
		with open(streamPath + '/info.txt') as infoFile:
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
			entries = feedparser.parse(self.rss)['entries']
			streamPath = f'{CATEGORY_DIR}/{self.categoryName}/{self.name}'
			i = 0
			if self.type == StreamType.DOWNLOADED:
				alreadyDownloaded = [entry for entry in sorted(os.listdir(streamPath)) if os.path.isfile(f'{streamPath}/{entry}') and entry != 'info.txt']
				latestDownloaded = alreadyDownloaded[-1].split(SEP, maxsplit=1)[0] if alreadyDownloaded else BEGINNING_OF_TIME
				while i < len(entries) - 1:
					pubParsed = self.findParsedDate(entries[i])
					itemDate = f'{pubParsed[0]}-{pubParsed[1]:02}-{pubParsed[2]:02}'
					if itemDate <= latestDownloaded:
						break
					i += 1

				# If this stream has been disabled but there are updates now, enable it.
				if self.currentDate == END_OF_TIME and i:
					pubParsed = self.findParsedDate(entries[i - 1])
					overwriteLineInFile(streamPath + '/info.txt', 2, f'{pubParsed[0]}-{pubParsed[1]:02}-{pubParsed[2]:02}\n')

				failures = 0
				start = max(len(alreadyDownloaded) + i - ITEM_LIMIT, 0)
				for j, entry in enumerate(reversed(entries[start:i])):
					pubParsed = self.findParsedDate(entry)
					itemDate = f'{pubParsed[0]}-{pubParsed[1]:02}-{pubParsed[2]:02}'
					itemName = entry.title.replace('/', '_').replace(SEP, '_')
					forceUpdateMessage(master, progressMessage, f'Downloading \'{itemName}\' ({j + 1} / {i - start}).')
					try:
						downloadUrl = next(link.href for link in entry.links if link.rel == 'enclosure')
					except StopIteration:
						print(f'My method for finding the link to download media files has failed for the item \'{itemName}\' in \'{self.name}\'.', file=sys.stderr)
						failures += 1
						if failures >= 3:
							# Give up on this stream.
							print(f'I am giving up on updating \'{self.name}\'.', file=sys.stderr)
							break
						else:
							continue
					# Attempt to get file extension from downloadUrl.
					extMatch = re.search(r'\.(\w+)([?#].*)?$', downloadUrl)
					if extMatch:
						itemExt = extMatch[1]
					else:
						continue
					try:
						urllib.request.urlretrieve(downloadUrl, f'{streamPath}/{itemDate}{SEP}{itemName}.{itemExt}')
					except urllib.error.URLError:
						print(f'Unable to download <{downloadUrl}> in {self.name}. Check your internet connection.', file=sys.stderr)
						failures += 1
						if failures >= 3:
							# Give up on this stream.
							break
				forceUpdateMessage(master, progressMessage, '')

			# Type is linked.
			else:
				# Downloading metadata is fast enough that there is no point trying to update for every item.
				with open(streamPath + '/queue.txt') as queueFile:
					queueLines = queueFile.readlines()
					latestSaved = queueLines[-1].split(SEP, maxsplit=1)[0] if queueLines else BEGINNING_OF_TIME
				while i < len(entries) - 1:
					pubParsed = self.findParsedDate(entries[i])
					itemDate = f'{pubParsed[0]}-{pubParsed[1]:02}-{pubParsed[2]:02}'
					if itemDate <= latestSaved:
						break
					i += 1

				# If this stream has been disabled but there are updates now, enable it.
				if self.currentDate == END_OF_TIME and i:
					pubParsed = self.findParsedDate(entries[i - 1])
					overwriteLineInFile(streamPath + '/info.txt', 2, f'{pubParsed[0]}-{pubParsed[1]:02}-{pubParsed[2]:02}\n')

				newItems = []
				for entry in reversed(entries[:i]):
					pubParsed = self.findParsedDate(entry)
					itemDate = f'{pubParsed[0]}-{pubParsed[1]:02}-{pubParsed[2]:02}'
					itemName = entry.title.replace(SEP, '_')
					itemUrl = entry.link
					newItems.append(f'{itemDate}{SEP}{itemName}{SEP}{itemUrl}\n')

				# We append to the file so that we don't overwrite any items already there.
				with open(streamPath + '/queue.txt', 'a', errors='replace') as queueFile:
					queueFile.writelines(newItems)

	@staticmethod
	def findParsedDate(entry):
		for key in ['published_parsed', 'updated_parsed']:
			try:
				return entry[key]
			except KeyError:
				continue
		raise ValueError('Failed to find the date for an entry.')

	def __repr__(self):
		return f'ContentStream({self.categoryName}, {self.name})'

	def __str__(self):
		return f'ContentStream \'{self.name}\' in category \'{self.categoryName}\''
	
	def __lt__(self, other):
		return self.currentDate < other.currentDate

	def __gt__(self, other):
		return self.currentDate > other.currentDate

class ContentCategory(tk.Frame):
	'''Represent a category of streams like 'Videos' or 'Favourites'. May contain multiple streams of different types.'''
	def __init__(self, master=None, name=None, column=0):
		super().__init__(master)
		self.name = name
		streamNames = [entry for entry in os.listdir(f'{CATEGORY_DIR}/{self.name}') if os.path.isdir(f'{CATEGORY_DIR}/{self.name}/{entry}')]
		self.streams = []
		for streamName in streamNames:
			self.streams.append(ContentStream(self.name, streamName))
		self.column = column
		self.draw()

	def completeCurrent(self):
		'''Advance the current stream by one item.'''
		cStream = self.currentStream
		streamPath = f'{CATEGORY_DIR}/{self.name}/{cStream.name}'

		# Get item list.
		if cStream.type == StreamType.DOWNLOADED:
			itemList = [entry for entry in sorted(os.listdir(streamPath)) if os.path.isfile(f'{streamPath}/{entry}') and entry != 'info.txt']
		# linked or manual.
		else:
			with open(streamPath + '/queue.txt') as queueFile:
				# Last char of each line is '\n'.
				itemList = [line[:-1] for line in queueFile.readlines()]

		# If there is no current.
		if not cStream.currentDate or cStream.currentDate == BEGINNING_OF_TIME:
			# Does not represent the last item in the list, but that the index of the "next" item is 0.
			oldIndex = -1
		# If the stream has been paused.
		elif cStream.currentDate == END_OF_TIME:
			oldIndex = len(itemList) - 1
		# For any stream type.
		else:
			oldIndex = next(i for i, item in enumerate(itemList) if item.startswith(f'{cStream.currentDate}{SEP}{cStream.currentName}'))

		# If current is last available.
		if oldIndex + 1 >= len(itemList):
			win = tk.Toplevel()
			win.title('End of stream')
			displayMessage(win, text='You have reached the end of this stream (until it is updated).', width=POPUP_WIDTH)
			displayButton(win, text='Close', command=win.destroy)
			# We need to temporarily disable this stream so that any other streams that still have next items can be displayed.
			cStream.currentDate = END_OF_TIME
		# There is a next one.
		else:
			# Update stream object.
			if cStream.type == StreamType.DOWNLOADED:
				currentInfo, cStream.currentExtension = itemList[oldIndex + 1].rsplit('.', maxsplit=1)
				cStream.currentDate, cStream.currentName = currentInfo.split(SEP, maxsplit=1)
			elif cStream.type == StreamType.LINKED:
				cStream.currentDate, cStream.currentName, cStream.currentUrl = itemList[oldIndex + 1].split(SEP, maxsplit=2)
			# manual.
			else:
				cStream.currentDate, cStream.currentName = itemList[oldIndex + 1].split(SEP, maxsplit=2)
		cStream.currentProgress = '0'

		# Update current in info file.
		infoLines = [cStream.type]
		if cStream.type != StreamType.MANUAL:
			infoLines.append(cStream.rss if cStream.rss else '')
		infoLines.append(cStream.currentDate)
		infoLines.append(cStream.currentName)
		if cStream.type == StreamType.DOWNLOADED:
			infoLines.append(cStream.currentExtension)
		elif cStream.type == StreamType.LINKED:
			infoLines.append(cStream.currentUrl)
		infoLines.append(cStream.currentProgress)
		infoLines.append('')

		with open(streamPath + '/info.txt', 'w') as infoFile:
			infoFile.writelines(line + '\n' for line in infoLines)

		# Update UI.
		self.grid_forget()
		self.draw()

	def draw(self):
		'''Draw all of the parts of this category.
		Not to be confused with display(), which is defined below and works on tkinter elements.'''
		# ContentCategory extends tk.Frame.
		display(self, row=0, column=self.column, rowspan=8)
		# Keep track of what rows have already been used. Putting every element in the first available row (regardless of what the type of the current stream is) means that manual streams will appear shorter than downloaded and linked, and the buttons that all streams have (eg "Open directory") will appear in different rows for different categories. But some users might only use manual streams, and some only downloaded and linked.
		rowIndex = 0
		displayMessage(self.master, text=self.name, width=CATEGORY_WIDTH, font=HEADER_FONT, row=rowIndex, column=self.column)
		rowIndex += 1
		if self.streams:
			self.currentStream = min(self.streams)
			cStream = self.currentStream
			streamPath = f'{CATEGORY_DIR}/{self.name}/{cStream.name}'
			displayMessage(self.master, text=cStream.name, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
			rowIndex += 1
			if cStream.type == StreamType.MANUAL:
				for text in (cStream.currentName, cStream.currentDate):
					displayMessage(self.master, text=text, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
					rowIndex += 1

			# Downloaded or linked.
			else:
				if cStream.currentName:
					displayMessage(self.master, text=cStream.currentName, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
				else:
					displayMessage(self.master, text='Click \'Current\' to advance to first item', width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
				rowIndex += 1
				displayMessage(self.master, text=cStream.currentDate, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
				rowIndex += 1

			# Progress displaying and saving. Here there is a difference between '' and None.
			self.currentProgressMessage = displayMessage(self.master, text=cStream.currentProgress, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
			rowIndex += 1
			self.progressEntry = tk.Entry(self.master, width=8, font=DEFAULT_FONT)
			display(self.progressEntry, row=rowIndex, column=self.column)
			rowIndex += 1
			def saveProgress():
				progress = self.progressEntry.get()
				infoPath = streamPath + '/info.txt'
				overwriteLineInFile(infoPath, 3 if cStream.type == StreamType.MANUAL else 5, progress)
				# Make update visible to user.
				self.currentProgressMessage.configure(text=progress)
			displayButton(self.master, text='Save progress', command=saveProgress, row=rowIndex, column=self.column)
			rowIndex += 1

			if cStream.type != StreamType.MANUAL:
				def openCurrent():
					if cStream.currentDate == BEGINNING_OF_TIME:
						win = tk.Toplevel()
						win.title('Empty stream')
						displayMessage(win, text='This stream does not yet contain any media items to open.', width=POPUP_WIDTH)
						displayButton(win, text='Close', command=win.destroy)
					else:
						if cStream.type == StreamType.DOWNLOADED:
							openMedia(f'{streamPath}/{cStream.currentDate}{SEP}{cStream.currentName}.{cStream.currentExtension}')
						# Linked.
						else:
							openMedia(cStream.currentUrl)
				displayButton(self.master, text='Open', command=openCurrent, row=rowIndex, column=self.column)
				rowIndex += 1

			displayButton(self.master, text='Complete', command=self.completeCurrent, row=rowIndex, column=self.column)
			rowIndex += 1
			def openInfoFile():
				openMedia(streamPath + '/info.txt')
			displayButton(self.master, text='Open info file', command=openInfoFile, row=rowIndex, column=self.column)
			rowIndex += 1

		# We have no streams.
		else:
			displayMessage(self.master, text='This category does not contain any streams.', width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
			rowIndex += 1

	def __repr__(self):
		return f'ContentCategory({self.master}, {self.name})'

	def __str__(self):
		return f'ContentCategory \'{self.name}\' with {len(self.streams)} streams'

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

def overwriteLineInFile(filepath, index, line):
	with open(filepath) as fileHandle:
		lines = fileHandle.readlines()
	lines[index] = line
	with open(filepath, 'w') as fileHandle:
		fileHandle.writelines(lines)

if __name__ == '__main__':
	main()
