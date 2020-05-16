'''
# Automated Content Consumption
A lightweight feed aggregator that supports manual creation of backlogs.
## `info.txt` format
### Downloaded and linked streams
stream type
RSS feed url (optional)
current item date (yyyy-mm-dd format)
current item name
current file extension or current url     # If this is the current extension, it should *not* include the period at the beginning of the extension.
currTime (optional)
                                          # This line is intentionally left blank so that when the file is read with readlines(), the last character of every line is '\n'.
### Manual streams
type
                                          # This line is intentionally left blank.
current item date (yyyy-mm-dd format)
current item name
current item author
                                          # This line is intentionally left blank so that when the file is read with readlines(), the last character of every line is '\n'.
## `queue.txt` format
yyyy-mm-dd;first item name with semicolons removed / replaced;first item url
yyyy-mm-dd;second item name;second item url
[...]
'''

# All the graphics.
import tkinter as tk
# Used to get the contents of directories, and determine whether something is a file or a directory.
import os
# Only needed for re.sub().
import re
# Used to tell the OS to open media files.
import subprocess
# Used to tell the OS to open webpages.
import webbrowser
# RSS metadata downloading.
import feedparser
# File downloading.
import urllib.request

# When downloading using RSS, a downloaded stream will stop downloading when this many items are saved locally. (Prevents using too much disk space.)
# Once this limit is reached, old files (that have been consumed) must be manually deleted.
ITEM_LIMIT = 1000000

# Name of directory containing all content data.
CATEGORY_DIR = 'categories'

# Name of memo file (where memo box data is stored).
MEMO_PATH = 'memo.txt'

CATEGORY_WIDTH = 200
POPUP_WIDTH = 500
ENTRY_WIDTH = 32

# Font defaults.
DEFAULT_FONT = ('Helvetica', 12)
HEADER_FONT = ('Courier', 20)

# Default padding for, like, everything.
PADX = 6
PADY = 6

# Default tk.Button wraplength value.
BUTTON_WRAP_LEN = 200

# Only dates strictly after the BEGINNING_OF_TIME and strictly before the END_OF_TIME are supported.
BEGINNING_OF_TIME = '1000-01-01'
END_OF_TIME = '9000-01-01'

STREAM_TYPES = ['downloaded', 'linked', 'manual']

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
		if not os.path.isdir(CATEGORY_DIR):
			os.mkdir(CATEGORY_DIR)
			self.intro()

		self.displayCategories()
		self.displayButtons()
		self.displayMemoBox()

	def intro(self):
		'''Display introductory message.'''
		win = tk.Toplevel(self.master)
		win.title('Introduction')
		with open('README.md', 'r') as introFile:
			intro = f'Hey, it looks like you might be new here. If so, let me explain how this works.\n{introFile.read()}'
		# A monospace font is used to display the info / queue file formatting correctly.
		introText = tk.Text(win, bg=win.cget('bg'), bd=0, font=('Courier', 12), width=100, wrap='word')
		introText.insert('end', intro)
		introText.tag_add('centered', '1.0', 'end')
		introText.tag_config('centered', justify='left')
		# Makes the text not editable.
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
		win.title('Updating feeds...')
		displayMessage(win, text='Updating RSS feeds (for all streams that have a defined RSS feed) in all categories. This may take a while, and, because of the (single-threaded) nature of Python, your OS will probably tell you that this program is not responding. It is probably fine and this program is probably not stuck, but just working hard.', width=POPUP_WIDTH)
		displayMessage(win, text='If you need to stop in the middle of updating, you probably stop in the middle of downloading a file (assuming you have at least one downloaded stream). If you pay attention to what stream is updating when you stop, then you can end this process and then manually delete the last media file in that stream (which will only be partially downloaded). This will put things in a stable state so that you can continue updating later.', width=POPUP_WIDTH)
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
			# We can't use 'type' as a variable name because it is a Python keyword.
			streamType = typeVar.get()
			name = nameVar.get()
			categoryName = categoryVar.get()
			rss = rssVar.get()
			streamPath = f'{CATEGORY_DIR}/{categoryName}/{name}'
			if not os.path.isdir(streamPath):
				os.mkdir(streamPath)
			infoLines = (streamType, rss, BEGINNING_OF_TIME, '', '', '')
			with open(f'{streamPath}/info.txt', 'w+') as infoFile:
				infoFile.writelines([f'{line}\n' for line in infoLines])
			if streamType == 'linked' and not os.path.isfile(f'{streamPath}/queue.txt'):
				open(f'{streamPath}/queue.txt', 'w').close()
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
				newStreamName = newStreamVar.get()
				if not newStreamName:
					newStreamName = oldStreamName
				newRss = rssVar.get()
				# Move stream directory.
				newStreamPath = f'{CATEGORY_DIR}/{newCategoryName}/{newStreamName}'
				os.rename(f'{CATEGORY_DIR}/{oldCategoryName}/{oldStreamName}', newStreamPath)
				# Update RSS.
				if newRss:
					with open(f'{newStreamPath}/info.txt', 'r') as infoFile:
						infoLines = infoFile.readlines()
					if oldStream.type != 'manual':
						infoLines[1] = f'{newRss}\n'
						with open(f'{newStreamPath}/info.txt', 'w') as infoFile:
							infoFile.writelines(infoLines)
						oldStream.rss = newRss
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
			with open(MEMO_PATH, 'r') as memoFile:
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

		# If the stream has files in it but there is no info file, assume the user created a downloaded stream of files and create an info file for it.
		# It is possible to make an assumption like this only for downloaded streams, because if a directory contains a queue file, it might be linked or manual.
		fileList = [entry for entry in sorted(os.listdir(streamPath)) if entry != 'info.txt' and entry != 'queue.txt']
		try:
			with open(f'{streamPath}/info.txt', 'r') as infoFile:
				# Save lines without their newlines.
				infoLines = [line[:-1] for line in infoFile.readlines()]
		except FileNotFoundError:
			if fileList:
				currentInfo, currentExtension = fileList[0].rsplit('.', maxsplit=1)
				currentDate, currentName = currentInfo.rsplit('-', maxsplit=1)
				infoLines = ('downloaded', '', currentDate, currentName, currentExtension, '')
				with open(f'{streamPath}/info.txt', 'x') as infoFile:
					infoFile.writelines([f'{line}\n' for line in infoLines])

		with open(f'{streamPath}/info.txt', 'r') as infoFile:
			# Save lines but chop newlines off of end of each line.
			infoLines = [line[:-1] for line in infoFile.readlines()]
		# Save values which are constant across all stream types.
		self.type, self.currentDate, self.currentName = infoLines[0], infoLines[2], infoLines[3]
		if self.type == 'manual':
			self.currentAuthor = infoLines[4]
			self.rss, self.currentExtension, self.currentUrl, self.currentTime = None, None, None, None
		# Type is either downloaded or linked.
		else:
			self.rss = infoLines[1] if infoLines[1] else None
			if self.type == 'downloaded':
				self.currentExtension = infoLines[4]
			# Type is linked.
			else:
				self.currentUrl = infoLines[4]
				if not os.path.isfile(f'{streamPath}/queue.txt'):
					open(f'{streamPath}/queue.txt', 'w+').close()

			self.currentTime = infoLines[5] if len(infoLines) > 5 else None
			self.currentAuthor = None

	def updateRSS(self, master, progressMessage):
		'''Get the RSS feed for this stream and download all new listed items (up to ITEM_LIMIT).'''
		if self.rss and (self.type == 'downloaded' or self.type == 'linked'):
			# Used by re.sub() to filter out chars that might make invalid file names or contain ';', which would mess with queue files.
			entries = feedparser.parse(self.rss).entries
			streamPath = f'{CATEGORY_DIR}/{self.categoryName}/{self.name}'
			i = 0
			if self.type == 'downloaded':
				alreadyDownloaded = [entry for entry in sorted(os.listdir(streamPath)) if os.path.isfile(f'{streamPath}/{entry}') and entry != 'info.txt']
				latestDownloaded = alreadyDownloaded[-1][:10] if alreadyDownloaded else BEGINNING_OF_TIME
				while i < len(entries) - 1:
					pubParsed = entries[i].published_parsed
					itemDate = f'{pubParsed[0]}-{pubParsed[1]:02}-{pubParsed[2]:02}'
					if itemDate <= latestDownloaded:
						break
					i += 1

				# If this stream has been disabled but there are updates now, enable it.
				with open(f'{streamPath}/info.txt', 'r') as infoFile:
					infoLines = infoFile.readlines()
				currentDate = infoLines[2][:-1]
				if currentDate == END_OF_TIME and entries:
					pubParsed = entries[i].published_parsed
					infoLines[2] = f'{pubParsed[0]}-{pubParsed[1]:02}-{pubParsed[2]:02}\n'
					with open(f'{streamPath}/info.txt', 'w') as infoFile:
						infoFile.writelines(infoLines)

				failures = 0
				start = max(len(alreadyDownloaded) + i - ITEM_LIMIT, 0)
				for j, entry in enumerate(reversed(entries[start:i])):
					pubParsed = entry.published_parsed
					itemDate = f'{pubParsed[0]}-{pubParsed[1]:02}-{pubParsed[2]:02}'
					itemName = entry.title.replace('/', '_')
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
					itemExt = re.sub(r'.*\.([a-zA-Z0-9]*).*', r'\1', downloadUrl)
					try:
						urllib.request.urlretrieve(downloadUrl, f'{streamPath}/{itemDate};{itemName}.{itemExt}')
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
				with open(f'{streamPath}/queue.txt', 'r') as queueFile:
					queueLines = queueFile.readlines()
					latestSaved = queueLines[-1][:10] if queueLines else BEGINNING_OF_TIME
				while i < len(entries) - 1:
					pubParsed = entries[i].published_parsed
					itemDate = f'{pubParsed[0]}-{pubParsed[1]:02}-{pubParsed[2]:02}'
					if itemDate <= latestSaved:
						break
					i += 1

				# If this stream has been disabled but there are updates now, enable it.
				with open(f'{streamPath}/info.txt', 'r') as infoFile:
					infoLines = infoFile.readlines()
				currentDate = infoLines[2][:-1]
				if currentDate == END_OF_TIME and entries:
					pubParsed = entries[i].published_parsed
					infoLines[2] = f'{pubParsed[0]}-{pubParsed[1]:02}-{pubParsed[2]:02}\n'
					with open(f'{streamPath}/info.txt', 'w') as infoFile:
						infoFile.writelines(infoLines)

				newItems = []
				for entry in reversed(entries[:i]):
					pubParsed = entry.published_parsed
					itemDate = f'{pubParsed[0]}-{pubParsed[1]:02}-{pubParsed[2]:02}'
					itemName = entry.title.replace(';', '_')
					itemUrl = entry.link
					newItems.append(f'{itemDate};{itemName};{itemUrl}\n')

				# We append to the file so that we don't overwrite any items already there.
				with open(f'{streamPath}/queue.txt', 'a') as queueFile:
					queueFile.writelines(newItems)

	def __repr__(self):
		return f'ContentStream({self.categoryName}, {self.name})'
	def __str__(self):
		return f'ContentStream \'{self.name}\' in category \'{self.categoryName}\''

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
		if cStream.type == 'downloaded':
			itemList = [entry for entry in sorted(os.listdir(streamPath)) if os.path.isfile(f'{streamPath}/{entry}') and entry != 'info.txt']
		# linked or manual.
		else:
			with open(f'{streamPath}/queue.txt', 'r') as queueFile:
				# Last line is always '\n', and last char of each line is '\n'.
				itemList = queueFile.readlines()[:-1][:-1]

		# If there is no current.
		if not cStream.currentDate or cStream.currentDate == BEGINNING_OF_TIME:
			# Does not represent the last item in the list, but that the index of the "next" item is 0.
			oldIndex = -1
		# If the stream has been paused.
		elif cStream.currentDate == END_OF_TIME:
			oldIndex = len(itemList) - 1
		# For any stream type.
		else:
			oldIndex = next(i for i, item in enumerate(itemList) if item.startswith(f'{cStream.currentDate};{cStream.currentName}'))

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
			if cStream.type == 'downloaded':
				currentInfo, cStream.currentExtension = itemList[oldIndex + 1].rsplit('.', maxsplit=1)
				cStream.currentDate, cStream.currentName = currentInfo[:10], currentInfo[11:]
			elif cStream.type == 'linked':
				cStream.currentDate, cStream.currentName, cStream.currentUrl = itemList[oldIndex + 1].split(';', maxsplit=2)
			# manual.
			else:
				cStream.currentDate, cStream.currentName, cStream.currentAuthor = itemList[oldIndex + 1].split(';', maxsplit=2)
		# Here there is a difference between '' and None.
		if cStream.currentTime != None:
			cStream.currentTime = '0:00'

		# Update current in info file.
		infoLines = [f'{cStream.type}\n']
		infoLines.append(f'{cStream.rss}\n' if cStream.rss else '\n')
		infoLines.append(f'{cStream.currentDate}\n')
		infoLines.append(f'{cStream.currentName}\n')
		if cStream.type == 'downloaded':
			infoLines.append(f'{cStream.currentExtension}\n')
		elif cStream.type == 'linked':
			infoLines.append(f'{cStream.currentUrl}\n')
		# manual
		else:
			infoLines.append(f'{cStream.currentAuthor}\n')
		if cStream.currentTime != None:
			infoLines.append(f'{cStream.currentTime}\n')
		infoLines.append('\n')

		with open(f'{streamPath}/info.txt', 'w') as infoFile:
			infoFile.writelines(infoLines)

		# Update UI.
		self.grid_forget()
		self.draw()

	def draw(self):
		'''Draw all of the parts of this category.
		Not to be confused with display(), which is defined below and works on tkinter elements.'''
		self.currentStream = min(self.streams, key=lambda f: f.currentDate) if self.streams else None
		cStream = self.currentStream
		# ContentCategory extends tk.Frame.
		display(self, row=0, column=self.column, rowspan=8)
		# Keep track of what rows have already been used. Putting every element in the first available row (regardless of what the type of the current stream is) means that manual streams will appear shorter than downloaded and linked, and the buttons that all streams have (eg "Open directory") will appear in different rows for different categories. But some users might only use manual streams, and some only downloaded and linked.
		rowIndex = 0
		self.headerMessage = displayMessage(self.master, text=self.name, width=CATEGORY_WIDTH, font=HEADER_FONT)
		display(self.headerMessage, row=rowIndex, column=self.column)
		rowIndex += 1
		if self.streams:
			streamPath = f'{CATEGORY_DIR}/{self.name}/{cStream.name}'
			displayMessage(self.master, text=cStream.name, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
			rowIndex += 1
			if cStream.type == 'manual':
				for text in (cStream.currentName, cStream.currentAuthor, cStream.currentDate):
					displayMessage(self.master, text=text, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
					rowIndex += 1

			# downloaded or linked
			else:
				if cStream.currentName:
					displayMessage(self.master, text=cStream.currentName, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
				else:
					displayMessage(self.master, text='Click \'Current\' to advance to first item', width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
				rowIndex += 1
				if cStream.currentDate:
					displayMessage(self.master, text=cStream.currentDate, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
				rowIndex += 1

				# Timestamp displaying and saving. Here there is a difference between '' and None.
				if cStream.currentTime:
					self.currentTimeMessage = displayMessage(self.master, text=cStream.currentTime, width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
					rowIndex += 1
					self.timeEntry = tk.Entry(self.master, width=ENTRY_WIDTH, font=DEFAULT_FONT)
					display(self.timeEntry, row=rowIndex, column=self.column)
					rowIndex += 1
					def saveTime():
						time = self.timeEntry.get()
						infoPath = f'{streamPath}/info.txt'
						with open(infoPath, 'r') as infoFile:
							lines = infoFile.readlines()
						lines[5] = time
						with open(infoPath, 'w') as infoFile:
							infoFile.writelines(lines)
						# Make update visible to user.
						self.currentTimeMessage.configure(text=time)
					displayButton(self.master, text='Save time', command=saveTime, row=rowIndex, column=self.column)
					rowIndex += 1
				# Button to open items for downloaded.
				if cStream.type == 'downloaded':
					def openCurrent():
						if cStream.currentDate == BEGINNING_OF_TIME:
							win = tk.Toplevel()
							win.title('Empty stream')
							displayMessage(win, text='This stream does not yet contain any media items to open.', width=POPUP_WIDTH)
							displayButton(win, text='Close', command=win.destroy)
						else:
							openMedia(f'{streamPath}/{cStream.currentDate};{cStream.currentName}.{cStream.currentExtension}')
					displayButton(self.master, text='Open', command=openCurrent, row=rowIndex, column=self.column)
					rowIndex += 1
				# Button to open items for linked.
				else:
					def openCurrent():
						openMedia(cStream.currentUrl)
					displayButton(self.master, text='Open', command=openCurrent, row=rowIndex, column=self.column)
					rowIndex += 1

			displayButton(self.master, text='Complete', command=self.completeCurrent, row=rowIndex, column=self.column)
			rowIndex += 1
			def openInfoFile():
				openMedia(f'{streamPath}/info.txt')
			displayButton(self.master, text='Open info file', command=openInfoFile, row=rowIndex, column=self.column)
			rowIndex += 1
		# We have no streams.
		else:
			displayMessage(self.master, text='This category does not contain any streams.', width=CATEGORY_WIDTH, row=rowIndex, column=self.column)
			rowIndex += 1
		# Whether we have streams or not.
		def openDirectory():
			openMedia(f'{CATEGORY_DIR}/{self.name}')
		displayButton(self.master, text='Open directory', command=openDirectory, row=rowIndex, column=self.column)
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
	entry = tk.Entry(win, width=ENTRY_WIDTH, font=DEFAULT_FONT)
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
			with open(os.devnull, 'wb') as devnull:
				subprocess.run(['xdg-open', filepath], stdout=devnull, stderr=subprocess.STDERR)

if __name__ == '__main__':
	main()
