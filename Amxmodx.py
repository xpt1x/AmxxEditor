# Sublime AMXX-Editor by Destro

import os
import re
import string
import sys
import sublime, sublime_plugin
import webbrowser
import datetime
import time
import urllib.request
from collections import defaultdict, OrderedDict
from queue import *
from threading import Timer, Thread

sys.path.append(os.path.dirname(__file__))
import watchdog.events
import watchdog.observers
import watchdog.utils
from watchdog.utils.bricks import OrderedSetQueue

from os.path import basename
import logging

CURRENT_PACKAGE_NAME = __package__
g_is_package_loading = True

def plugin_unloaded():
#{
	global g_is_package_loading
	g_is_package_loading=True

	settings = sublime.load_settings("Amxmodx.sublime-settings")
	settings.clear_on_change('Amxmodx')
#}

def plugin_loaded():
#{
	settings = sublime.load_settings("Amxmodx.sublime-settings")

	install_build_systens("AmxxPawn.sh")
	install_build_systens("AmxxPawn.bat")

	install_setting_file("Amxmodx.sublime-settings")
	install_setting_file("AmxmodxConsole.sublime-settings")

	# Fixes the settings dialog showing up when installing the package for the first time
	global g_is_package_loading

	g_is_package_loading=True
	sublime.set_timeout( unlock_is_package_loading, 10000 )

	on_settings_modified();
	settings.add_on_change('Amxmodx', on_settings_modified)
#}

def unlock_is_package_loading():
#{
	global g_is_package_loading
	g_is_package_loading = False
#}

def install_build_systens(target_file_name):
#{
	target_folder     = "Amxmodx"
	target_file       = os.path.join( sublime.packages_path(), "User", target_folder, target_file_name )
	input_file_string = sublime.load_resource( "Packages/%s/%s" % ( CURRENT_PACKAGE_NAME, target_file_name ) )

	target_directory = os.path.join( sublime.packages_path(), "User", target_folder )
	attempt_to_install_file( target_directory, target_file, input_file_string )
#}

def install_setting_file( target_file_name ):
#{
	target_file       = os.path.join( sublime.packages_path(), "User", target_file_name )
	input_file_string = sublime.load_resource( "Packages/%s/%s" % ( CURRENT_PACKAGE_NAME, target_file_name ) )

	target_directory = os.path.join( sublime.packages_path(), "User" )
	attempt_to_install_file( target_directory, target_file, input_file_string )
#}

def attempt_to_install_file( target_directory, target_file, input_file_string ):
#{
	if not os.path.exists( target_directory ):
		os.makedirs( target_directory )

	# How can I force Python's file.write() to use the same newline format in Windows as in Linux (“\r\n” vs. “\n”)?
	# https://stackoverflow.com/questions/9184107/how-can-i-force-pythons-file-write-to-use-the-same-newline-format-in-windows
	#
	# TypeError: 'str' does not support the buffer interface
	# https://stackoverflow.com/questions/5471158/typeerror-str-does-not-support-the-buffer-interface
	if not os.path.exists( target_file ):
		text_file = open( target_file, "wb" )
		text_file.write( bytes(input_file_string, 'UTF-8') )
		text_file.close()
#}

def unload_handler() :
#{
	file_observer.stop()
	process_thread.stop()

	processingSetQueue.put(("", ""))
	sublime.load_settings("%s.sublime-settings" % CURRENT_PACKAGE_NAME).clear_on_change(CURRENT_PACKAGE_NAME)
#}

class NewAmxxIncludeCommand(sublime_plugin.WindowCommand):
	def run(self):
		new_file("inc")


class NewAmxxPluginCommand(sublime_plugin.WindowCommand):
	def run(self):
		new_file("sma")


def new_file(file_type):
#{
	view = sublime.active_window().new_file()
	view.set_name("untitled."+file_type)

	plugin_template = sublime.load_resource("Packages/%s/default.%s" % (CURRENT_PACKAGE_NAME, file_type))
	plugin_template = plugin_template.replace("\r", "")

	view.run_command("insert_snippet", {"contents": plugin_template})
	sublime.set_timeout_async( lambda: set_new_file_syntax( view ), 0 )
#}

def set_new_file_syntax( view ):
	view.set_syntax_file(g_new_file_syntax)


class AboutAmxxEditorCommand(sublime_plugin.WindowCommand):
#{
	def run(self):
	#{
		about = "Sublime AMXX-Editor v"+ EDITOR_VERSION +" by Destro\n\n\n"

		about += "CREDITs:\n"
		about += "- Great:\n"
		about += "   ppalex7     (SourcePawn Completions)\n\n"

		about += "- Contributors:\n"
		about += "   sasske        (white color scheme)\n"
		about += "   addons_zz     (npp color scheme)\n"
		about += "   KliPPy        (build version)\n"
		about += "   Mistrick      (mistrick color scheme)\n"

		about += "\nhttps://amxmodx-es.com/showthread.php?tid=12316\n"

		sublime.message_dialog(about)
	#}
#}

class AmxxBuildVerCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		region = self.view.find("^#define\s+(?:PLUGIN_)?VERSION\s+\".+\"", 0, sublime.IGNORECASE)
		if region == None :
			region = self.view.find("new\s+const\s+(?:PLUGIN_)?VERSION\s*\[\s*\]\s*=\s*\".+\"", 0, sublime.IGNORECASE)
			if region == None :
				return

		line = self.view.substr(region)
		result = re.match("(.*\"(?:v)?\d{1,2}\.\d{1,2}\.(?:\d{1,2}-)?)(\d+)(b(?:eta)?)?\"", line)
		if not result :
			return

		build = int(result.group(2))
		build += 1

		beta = result.group(3)
		if not beta :
			beta = ""

		self.view.replace(edit, region, result.group(1) + str(build) + beta + '\"')

class AMXXEditor(sublime_plugin.EventListener):
	def __init__(self) :
		process_thread.start()
		self.delay_queue = None
		file_observer.start()

	def on_window_command(self, window, cmd, args) :
		if cmd != "build" :
			return

		view = window.active_view()
		if not is_amxmodx_file(view) or not g_enable_buildversion :
			return

		view.run_command("amxx_build_ver")

	def on_selection_modified_async(self, view) :
		if not is_amxmodx_file(view) or not g_enable_inteltip :
			return

		region = view.sel()[0]
		scope = view.scope_name(region.begin())
		print_debug(4, "(inteltip) scope_name: [%s]" % scope)

		if not "support.function" in scope and not "include_path.pawn" in scope or region.size() > 1 :
			view.hide_popup()
			view.add_regions("inteltip", [ ])
			return

		if "include_path.pawn" in scope :
			self.inteltip_include(view, region)
		else :
			self.inteltip_function(view, region)

	def inteltip_include(self, view, region) :

		location = view.word(region).end() + 1
		line     = view.substr(view.line(region))
		include  = includes_re.match(line).group(1)

		file_name_view = view.file_name()

		if file_name_view is None:
			return
		else:
			( file_name, the_include_exists ) = get_file_name( file_name_view, include )

			if not the_include_exists :
				return

		link_local = file_name + '#'
		if not '.' in include :
			link_web = include + '#'
			include += ".inc"
		else :
			link_web = None

		html  = '<style>'+ g_inteltip_style +'</style>'
		html += '<div class="top">'
		html += '<a class="file" href="'+link_local+'">'+include+'</a>'
		if link_web :
			html += ' | <a class="file" href="'+link_web+'">WebAPI</a>'

		html += '</div><div class="bottom">'

		html += '<span class="func_type">Location:</span><br>'
		html += '<span class="func_name">'+file_name+'</span>'
		html += '</div>'

		view.show_popup(html, 0, location, max_width=700, on_navigate=self.on_navigate)

	def inteltip_function(self, view, region) :

		word_region = view.word(region)
		location 	= word_region.end() + 1
		search_func = view.substr(word_region)
		doctset 	= set()
		visited 	= set()
		found 		= None
		node 		= nodes[view.file_name()]

		self.generate_doctset_recur(node, doctset, visited)

		for func in doctset :
			if search_func == func[0] :
				found = func
				if found[3] != 1 :
					break

		if found:
			print_debug(1, "param2: [%s]" % simple_escape(found[1]))
			filename = os.path.basename(found[2])


			if found[3] :
				if found[4] :
					link_local = found[2] + '#' + FUNC_TYPES[found[3]] + ' ' + found[4] + ':' + found[0]
				else :
					link_local = found[2] + '#' + FUNC_TYPES[found[3]] + ' ' + found[0]

				link_web = filename.rsplit('.', 1)[0] + '#' + found[0]
			else :

				link_local = found[2] + '#' + '^' + found[0]
				link_web = ''

			html  = '<style>'+ g_inteltip_style +'</style>'
			html += '<div class="top">'							############################## TOP

			html += '<a class="file" href="'+link_local+'">'+os.path.basename(found[2])+'</a>'
			if link_web:
				html += ' | <a class="file" href="'+link_web+'">WebAPI</a>'

			html += '</div><div class="bottom">'		############################## BOTTOM

			html += '<span class="func_type">'+FUNC_TYPES[found[3]]+':</span> <span class="func_name">'+found[0]+'</span>'
			html += '<br>'
			html += '<span class="params">Params:</span> <span class="params_definition">('+ simple_escape(found[1]) +')</span>'
			html += '<br>'

			if found[4] :
				html += '<span class="return">Return:</span> <span class="return_type">'+found[4]+'</span>'

			html += '</div>'									############################## END

			view.show_popup(html, 0, location, max_width=700, on_navigate=self.on_navigate)
			view.add_regions("inteltip", [ word_region ], "inteltip.pawn")

		else:
			view.hide_popup()
			view.add_regions("inteltip", [ ])

	def on_navigate(self, link) :
		(file, search) = link.split('#')

		if "." in file :
			view = sublime.active_window().open_file(file);
			def do_position() :
				if view.is_loading():
					sublime.set_timeout(do_position, 100)
				else :
					r=view.find(search, 0, sublime.IGNORECASE)

					view.sel().clear()
					view.sel().add(r)

					view.show(r)
			do_position()
		else :
			webbrowser.open_new_tab("http://www.amxmodx.org/api/"+file+"/"+search)

	def on_activated_async(self, view) :

		view_size = view.size()

		print_debug(4, "on_activated_async(2)")
		print_debug(4, "( on_activated_async ) view.match_selector(0, 'source.sma'): " + str( view.match_selector(0, 'source.sma') ))

		# print_debug(4, "( on_activated_async ) nodes: " + str( nodes ))
		print_debug(4, "( on_activated_async ) view.substr(): \n" \
				+ view.substr( sublime.Region( 0, view_size if view_size < 200 else 200 ) ))

		if not is_amxmodx_file(view):
			print_debug(4, "( on_activated_async ) returning on` if not is_amxmodx_file(view)")
			return

		if not view.file_name() in nodes :
			print_debug(4, "( on_activated_async ) returning on` if not view.file_name() in nodes")
			add_to_queue(view)

	def on_modified_async(self, view) :
		self.add_to_queue_delayed(view)

	def on_post_save_async(self, view) :
		self.add_to_queue_now(view)

	def on_load_async(self, view) :
		self.add_to_queue_now(view)

	def add_to_queue_now(self, view) :
		if not is_amxmodx_file(view):
			return
		add_to_queue(view)

	def add_to_queue_delayed(self, view) :
		if not is_amxmodx_file(view):
			return

		if self.delay_queue is not None :
			self.delay_queue.cancel()

		self.delay_queue = Timer( float( g_delay_time ), add_to_queue_forward, [ view ] )
		self.delay_queue.start()

	def on_query_completions(self, view, prefix, locations):
		"""
			This is a forward called by Sublime Text when it is about to show the use completions.
			See: https://www.sublimetext.com/docs/3/api_reference.html#sublime_plugin.ViewEventListener
		"""
		view_file_name = view.file_name()

		if is_amxmodx_file(view):

			# temporarily masking word_separators
			# https://github.com/SublimeTextIssues/Core/issues/819
			word_separators = view.settings().get("word_separators")
			view.settings().set("word_separators", "")
			sublime.set_timeout(lambda: view.settings().set("word_separators", word_separators), 0)

			if view_file_name is None:
				view_file_name = str( view.buffer_id() )

				# Just in case it is not processed yet
				if not view_file_name in nodes:

					print_debug(4, "( on_query_completions ) Adding buffer id " + view_file_name + " in nodes")
					add_to_queue_forward( view )

					# The queue is not processed yet, so there is nothing to show
					if g_word_autocomplete:
						print_debug( 16, "(new buffer) Word autocomplete")
						return None
					else:
						print_debug( 16, "(new buffer) Without word autocomplete")
						return ( [], sublime.INHIBIT_WORD_COMPLETIONS )

				if g_word_autocomplete:
					print_debug( 16, "(Buffer) Word autocomplete + function")
					return self.generate_funcset( view_file_name, view, prefix, locations )
				else:
					print_debug( 16, "(Buffer) Without word autocomplete + function")
					return ( self.generate_funcset( view_file_name, view, prefix, locations ), sublime.INHIBIT_WORD_COMPLETIONS )
			else:

				if g_word_autocomplete:
					print_debug( 16, "(File) Word autocomplete + function")
					return self.generate_funcset( view_file_name, view, prefix, locations )
				else:
					print_debug( 16, "(File) Without word autocomplete + function")
					return ( self.generate_funcset( view_file_name, view, prefix, locations ), sublime.INHIBIT_WORD_COMPLETIONS )

		print_debug( 16, "No completions")
		return None

	def generate_funcset( self, file_name, view, prefix, locations ) :
		words_list = []
		func_list = []
		func_word_list = []

		if file_name in nodes:
			node    = nodes[file_name]
			visited = set()

			if not view.match_selector(locations[0], 'string') :
				self.generate_funcset_recur( node, visited, func_list, func_word_list )

		if g_word_autocomplete:
			start_time = time.time()

			if len( locations ) > 0:
				view_words = view.extract_completions( prefix, locations[0] )

			else:
				view_words = view.extract_completions( prefix )

			# This view goes first to prioritize matches close to cursor position.
			for word in view_words:
				# Remove the annoying `(` on the string
				word = word.replace('$', '\\$').split('(')[0]

				if word not in func_word_list:
					words_list.append( ( word, word ) )

				if time.time() - start_time > 0.05:
					break

		# print_debug( 16, "( generate_funcset ) func_list size: %d" % len( func_list ) )
		# print_debug( 16, "( generate_funcset ) func_list items: " + str( sort_nicely( func_list ) ) )
		return words_list + func_list

	def generate_funcset_recur( self, node, visited, func_list, func_word_list ) :

		if node in visited :
			return

		visited.add( node )

		for child in node.children :
			self.generate_funcset_recur( child, visited, func_list, func_word_list )

		func_list.extend( node.funcs )
		func_word_list.extend( node.func_words )

	def generate_doctset_recur(self, node, doctset, visited) :
		if node in visited :
			return

		visited.add(node)
		for child in node.children :
			self.generate_doctset_recur(child, doctset, visited)

		doctset.update(node.doct)


def is_amxmodx_file(view) :
	return view.match_selector(0, 'source.sma')


def on_settings_modified():
#{
	print_debug(4, "on_settings_modified" )
	global g_enable_inteltip
	global g_new_file_syntax
	global g_word_autocomplete
	global g_function_autocomplete

	settings = sublime.load_settings("Amxmodx.sublime-settings")
	invalid  = is_invalid_settings(settings)

	if invalid:
	#{
		if not g_is_package_loading:
			sublime.message_dialog("AMXX-Editor:\n\n" + invalid)

		g_enable_inteltip = 0
		return
	#}

	# check package path
	packages_path = os.path.join( sublime.packages_path(), CURRENT_PACKAGE_NAME )
	if not os.path.isdir(packages_path) :
		os.mkdir(packages_path)

	# fix-path
	fix_path(settings, 'include_directory')

	# Get the set color scheme
	popup_color_scheme = settings.get('popup_color_scheme')

	# popUp.CSS
	global g_inteltip_style
	g_inteltip_style = sublime.load_resource("Packages/%s/%s-popup.css" % (CURRENT_PACKAGE_NAME, popup_color_scheme))
	g_inteltip_style = g_inteltip_style.replace("\r", "") # fix win/linux newlines

	# cache setting
	global g_enable_buildversion, g_debug_level, g_delay_time, g_include_dir, g_add_paremeters

	g_enable_inteltip 		= settings.get('enable_inteltip', True)
	g_enable_buildversion 	= settings.get('enable_buildversion', False)
	g_word_autocomplete 	= settings.get('word_autocomplete', False)
	g_function_autocomplete = settings.get('function_autocomplete', False)
	g_new_file_syntax       = settings.get('amxx_file_syntax', 'Packages/%s/Amxmodx.sublime-syntax' % CURRENT_PACKAGE_NAME)
	g_debug_level 			= settings.get('debug_level', 0)
	g_delay_time			= settings.get('live_refresh_delay', 1.0)
	g_include_dir 			= settings.get('include_directory')
	g_add_paremeters		= settings.get('add_function_parameters', False)

	print_debug(4, "( on_settings_modified ) g_debug_level: %d" % g_debug_level)
	print_debug(4, "( on_settings_modified ) g_include_dir: " + g_include_dir)
	print_debug(4, "( on_settings_modified ) g_add_paremeters: " + str( g_add_paremeters ))

	file_observer.unschedule_all()
	file_observer.schedule( file_event_handler, g_include_dir, True )
#}

def is_invalid_settings(settings):
	general_error = "You are not set correctly settings for AMXX-Editor.\n\n"
	setting_names = [ "include_directory", "popup_color_scheme", "amxx_file_syntax" ]

	for setting_name in setting_names:
		result = general_settings_checker( settings, setting_name, general_error )

		if result:
			return result

	path_settings = \
	[
		( "include_directory", "F:\\SteamCMD\\steamapps\\common\\Half-Life\\czero\\addons\\amxmodx\\scripting\\include", "" ),
		( "amxx_file_syntax", "Packages/Amxmodx/AmxmodxPawn.sublime-syntax", os.path.dirname( sublime.packages_path() ) )
	]

	for setting_name, default_value, path_prefix in path_settings:
		result = path_settings_checker( settings, setting_name, default_value, path_prefix )

		if result:
			return result


def general_settings_checker(settings, settings_name, general_error):
	setting_value = settings.get( settings_name )

	if setting_value is None:
		return general_error + "Missing `%s` value." % settings_name


def path_settings_checker(settings, settings_name, default_value, prefix_path=""):
	setting_value = settings.get( settings_name )

	if setting_value != default_value:
		full_path = os.path.join( prefix_path, setting_value )

		if not os.path.exists( full_path ):
			lines = \
			[
				"The setting `%s` is not configured correctly. The following path does not exists:\n\n" % settings_name,
				str( setting_value ),
				"\n\nPlease, go to the following menu and fix the setting:\n\n"
				"`Amx Mod X -> Configure AMXX-Autocompletion Settings`\n\n",
				"`Preferences -> Packages Settings -> Amx Mod X -> Configure AMXX-Autocompletion Settings`",
			]

			return "".join( lines )


def fix_path(settings, key) :
#{
	org_path = settings.get(key)

	if org_path is "${file_path}" :
		return

	path = os.path.normpath(org_path)
	if os.path.isdir(path):
		path += '/'

	settings.set(key, path)
#}

def sort_nicely( words_set ):
	"""
		Sort the given iterable in the way that humans expect.
	"""
	convert = lambda text: int(text) if text.isdigit() else text
	alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key[0]) ]

	return sorted( words_set, key = alphanum_key )

def add_to_queue_forward(view) :
	sublime.set_timeout_async( lambda: add_to_queue( view ), float( g_delay_time ) * 1000.0 )

def add_to_queue(view) :
	"""
		The view can only be accessed from the main thread, so run the regex
		now and process the results later
	"""
	print_debug(4, "( add_to_queue ) view.file_name(): " + str( view.file_name() ))

	# When the view is not saved, we need to use its buffer id, instead of its file name.
	view_file_name = view.file_name()

	if view_file_name is None :
		name = str( view.buffer_id() )

		if name not in processingSetQueue_set:
			processingSetQueue_set.add( name )
			processingSetQueue.put( ( name, view.substr( sublime.Region( 0, view.size() ) ) ) )
	else :
		if view_file_name not in processingSetQueue_set:
			processingSetQueue_set.add( view_file_name )
			processingSetQueue.put( ( view_file_name, view.substr( sublime.Region( 0, view.size() ) ) ) )

def add_include_to_queue(file_name) :
	if file_name not in processingSetQueue_set:
		processingSetQueue_set.add( file_name )
		processingSetQueue.put((file_name, None))

class IncludeFileEventHandler(watchdog.events.FileSystemEventHandler) :
	def __init__(self) :
		watchdog.events.FileSystemEventHandler.__init__(self)

	def on_created(self, event) :
		sublime.set_timeout(lambda: on_modified_main_thread(event.src_path), 0)

	def on_modified(self, event) :
		sublime.set_timeout(lambda: on_modified_main_thread(event.src_path), 0)

	def on_deleted(self, event) :
		sublime.set_timeout(lambda: on_deleted_main_thread(event.src_path), 0)

def on_modified_main_thread(file_path) :
	if not is_active(file_path) :
		add_include_to_queue(file_path)

def on_deleted_main_thread(file_path) :
	if is_active(file_path) :
			return

	node = nodes.get(file_path)
	if node is None :
		return

	node.remove_all_children_and_funcs()

def is_active(file_name) :
	return sublime.active_window().active_view().file_name() == file_name

class ProcessQueueThread(watchdog.utils.DaemonThread) :
	def run(self) :
		while self.should_keep_running() :
			(file_name, view_buffer) = processingSetQueue.get()

			try:
				processingSetQueue_set.remove( file_name )
			except:
				pass

			# When the `view_buffer` is None, it means we are processing a file on the disk, instead
			# of a file on an Sublime Text View (its text buffer).
			if view_buffer is None :
				self.process_existing_include(file_name)
			else :
				self.process(file_name, view_buffer)

	def process(self, view_file_name, view_buffer) :
		base_includes = set()
		(current_node, node_added) = get_or_add_node(view_file_name)

		# Here we parse the text file to know which modules it is including.
		includes = includes_re.findall(view_buffer)

		# Now for each module it is including we load that include file to the autocomplete list.
		for include in includes:
			self.load_from_file(view_file_name, include, current_node, current_node, base_includes)

		# For each module it was loaded but it not present on the current file we just switched,
		# we remove that include file to the autocomplete list.
		for removed_node in current_node.children.difference(base_includes) :
			current_node.remove_child(removed_node)

		# To process the current file functions for autocomplete
		process_buffer(view_buffer, current_node)

	def process_existing_include(self, file_name) :
		current_node = nodes.get(file_name)
		if current_node is None :
			return

		base_includes = set()

		with open(file_name, 'r') as f :
			print_debug(2, "(analyzer) Processing Include File %s" % file_name)
			includes = includes_re.findall(f.read())

		for include in includes:
			self.load_from_file(file_name, include, current_node, current_node, base_includes)

		for removed_node in current_node.children.difference(base_includes) :
			current_node.remove_child(removed_node)

		process_include_file(current_node)


	def load_from_file(self, view_file_name, base_file_name, parent_node, base_node, base_includes) :

		(file_name, exists) = get_file_name(view_file_name, base_file_name)

		if not exists :
			print_debug(1, "(analyzer) Include File Not Found: %s" % base_file_name)

		(node, node_added) = get_or_add_node(file_name)
		parent_node.add_child(node)

		if parent_node == base_node :
			base_includes.add(node)

		if not node_added or not exists:
			return

		with open(file_name, 'r') as f :
			print_debug(2, "(analyzer) Processing Include File %s" % file_name)
			includes = includes_re.findall(f.read())

		for include in includes :
			self.load_from_file(view_file_name, include, node, base_node, base_includes)

		process_include_file(node)


def get_file_name(view_file_name, base_file_name) :

	print_debug(4, "get_file_name: " + g_include_dir)

	if local_re.search(base_file_name) == None:
		file_name = os.path.join(g_include_dir, base_file_name + '.inc')
	else:
		file_name = os.path.join(os.path.dirname(view_file_name), base_file_name)

	return (file_name, os.path.exists(file_name))

def get_or_add_node(file_name) :
	"""
		Here if `file_name` is a buffer id as a string, I just check if the buffer exists.

		However if it is a file name, I need to check if its a buffer id is present here, and
		if so, I must to remove it and create a new node with the file name. This is necessary
		because the file could be just create, parsed and then saved. Therefore after did so,
		we need to keep reusing its buffer. But as it is saved we are using its file name instead
		of its buffer id, then we need to remove the buffer id in order to avoid duplicated entries.

		Though I am not implementing this here to save time and performance
	"""

	node = nodes.get(file_name)
	if node is None :
		node = Node(file_name)
		nodes[file_name] = node
		return (node, True)

	return (node, False)

# ============= NEW CODE ------------------------------------------------------------------------------------------------------------
class Node :
#{
	def __init__(self, file_name) :
		self.file_name = file_name

		self.doct = set()
		self.children = set()
		self.parents = set()

		# They are list to keep ordering
		self.funcs = []
		self.func_words = []

		try:
			float(file_name)
			self.isFromBufferOnly = True
		except ValueError:
			self.isFromBufferOnly = False

	def add_child(self, node) :
		self.children.add(node)
		node.parents.add(self)

	def remove_child(self, node) :
		self.children.remove(node)
		node.parents.remove(self)

		if len(node.parents) <= 0 :
			nodes.pop(node.file_name)

	def remove_all_children_and_funcs(self) :
		for child in self.children :
			self.remove_child(node)

		self.doct.clear()
		self.funcs.clear()
		self.func_words.clear()

class TextReader:
#{
	def __init__(self, text):
		self.text = text.splitlines()
		self.position = -1

	def readline(self) :
	#{
		self.position += 1

		if self.position < len(self.text) :
			retval = self.text[self.position]
			if retval == '' :
				return '\n'
			else :
				return retval
		else :
			return ''
	#}
#}

class PawnParse :
#{
	def __init__(self) :
		self.node = None
		self.isTheCurrentFile = False
		self.save_const_timer = None
		self.constants_count = 0

	def start( self, pFile, node, isTheCurrentFile=False ) :
		"""
			When the buffer is not None, it is always the current file.
		"""
		print_debug(8, "(analyzer) CODE PARSE Start [%s]" % node.file_name)

		self.isTheCurrentFile   = isTheCurrentFile
		self.file 				= pFile
		self.file_name			= os.path.basename(node.file_name)
		self.node 				= node
		self.found_comment 		= False
		self.found_enum 		= False
		self.is_to_skip_brace 	= False
		self.enum_contents 		= ''
		self.brace_level 		= 0
		self.restore_buffer 	= None

		self.is_to_skip_next_line     = False
		self.if_define_brace_level    = 0
		self.else_defined_brace_level = 0

		self.if_define_level   = 0
		self.else_define_level = 0

		self.is_on_if_define   = []
		self.is_on_else_define = []

		self.node.doct.clear()
		self.node.funcs.clear()
		self.node.func_words.clear()

		self.start_parse()

		if self.constants_count != len(g_constants_list) :
		#{
			if self.save_const_timer :
				self.save_const_timer.cancel()

			self.save_const_timer = Timer(4.0, self.save_constants)
			self.save_const_timer.start()
		#}

		print_debug(8, "(analyzer) CODE PARSE End [%s]" % node.file_name)
	#}

	def save_constants(self) :
	#{
		self.save_const_timer = None
		self.constants_count  = len(g_constants_list)
		windows               = sublime.windows()

		# If you have a project within 10000 files, each time this is updated, will for sublime to
		# process again all the files. Therefore only allow this on project with no files to index.
		#
		# If someone is calling this, it means there are some windows with a AMXX file open. Therefore
		# we do not care to check whether that window has a project or not and there will always be
		# constants to save.
		for window in windows:
			# print_debug(4, "(save_constants) window.id(): " + str( window.id() ) )
			# print_debug(4, "(save_constants) window.folders(): " + str( window.folders() ) )
			# print_debug(4, "(save_constants) window.project_file_name(): " + str( window.project_file_name() ) )

			if len( window.folders() ) > 0:
				print_debug( 4, "(save_constants) Not saving this time." )
				return

		constants = "___test"
		for const in g_constants_list :
			constants += "|" + const

		syntax = "%YAML 1.2\n---\nscope: source.sma\ncontexts:\n  main:\n    - match: \\b(" \
				+ constants + ")\\b\s*(?!\()\n      scope: constant.vars.pawn\n\n"

		file_name = os.path.join(sublime.packages_path(), CURRENT_PACKAGE_NAME, "const.sublime-syntax")

		f = open(file_name, 'w')
		f.write(syntax)
		f.close()

		print_debug(8, "(analyzer) call save_constants()")
	#}

	def read_line(self) :
	#{
		if self.restore_buffer :
			line = self.restore_buffer
			self.restore_buffer = None
		else :
			line = self.file.readline()

		if len(line) > 0 :
			return line
		else :
			return None
	#}

	def read_string(self, buffer) :
	#{
		buffer = buffer.replace('\t', ' ').strip()
		while '  ' in buffer :
			buffer = buffer.replace('  ', ' ')

		buffer = buffer.lstrip()

		result = ''
		i = 0

		# print_debug( 1, str( buffer ) )
		buffer_length = len(buffer)

		while i < buffer_length :
			if buffer[i] == '/' and i + 1 < len(buffer):
				if buffer[i + 1] == '/' :
					self.brace_level +=  result.count('{') - result.count('}')
					return result
				elif buffer[i + 1] == '*' :
					self.found_comment = True
					i += 1
				elif not self.found_comment :
					result += '/'
			elif self.found_comment :
				if buffer[i] == '*' and i + 1 < len(buffer) and buffer[i + 1] == '/' :
					self.found_comment = False
					i += 1
			elif not (i > 0 and buffer[i] == ' ' and buffer[i - 1] == ' '):
				result += buffer[i]

			i += 1

		self.brace_level +=  result.count('{') - result.count('}')
		return result
	#}

	def skip_function_block(self, buffer) :
	#{
		inChar    = False
		inString  = False
		num_brace = 0

		buffer                = buffer + ' '
		self.is_to_skip_brace = False

		while buffer is not None and buffer.isspace() :
			buffer = self.read_line()

		while buffer is not None :
		#{
			# print_debug( 32, "skip_function_block:      " + buffer )

			i               = 0
			pos             = 0
			lastChar        = ''
			penultimateChar = ''

			for c in buffer :
			#{
				i += 1

				if not inString and not inChar and lastChar == '*' and c == '/' :
					self.found_comment = False

				if not inString and not inChar and self.found_comment:
					penultimateChar = lastChar
					lastChar        = c
					continue

				if not inString and not inChar and lastChar == '/' and c == '*' :
					self.found_comment = True
					penultimateChar    = lastChar
					lastChar           = c
					continue

				if not inString and not inChar and c == '/' and lastChar == '/' :
					break

				if c == '"' :

					if inString and lastChar != '^' :
						inString = False

					else :
						inString = True

				if not inString and c == '\'' :

					if inChar and lastChar != '^' :
						inChar = False

					else :
						inChar = True

				# This is hard stuff. We need to fix the parsing for the following problem:
				#
				# public on_damage(id)
				# {
				# #if defined DAMAGE_RECIEVED
				#     if ( is_user_connected(id) && is_user_connected(attacker) )
				#     {
				# #else
				#     if ( is_user_connected(attacker) )
				#     {
				# #endif
				#     }
				#     return PLUGIN_CONTINUE
				# }
				# public death_hook()
				# {
				#     {
				#         new kuid = get_user_userid(killer)
				#     }
				# }
				#
				# Above here we may notice, there are 2 braces opening but only one brace close.
				# Therefore, we will skip the rest of the source code if we do not handle the braces
				# definitions between the `#if` and `#else` macro clauses.
				#
				# To keep track about where we are, we need to keep track about how much braces
				# levels are being opened and closed using the variables `self.if_define_brace_level`
				# and `self.else_defined_brace_level`. And finally at the end of it all on the `#endif`,
				# we update the `num_brace` with the correct brace level.
				#
				if not inString and not inChar :
				#{
					# Flags when we enter and leave the `#if ... #else ... #endif` blocks
					if penultimateChar == '#':

						# Cares of `#if`
						if lastChar == 'i' and c == 'f':
							++self.if_define_level
							self.is_on_if_define.append( True )

						# Cares of `#else` and `#end`
						elif lastChar == 'e':

							if c == 'l':
								++self.else_define_level
								self.is_on_if_define.append( False )
								self.is_on_else_define.append( True )

							elif c == 'n':

								# Decrement the `#else` level, only if it exists
								if len( self.is_on_if_define ) > 0:

									if not self.is_on_if_define[ -1 ]:
										self.is_on_if_define.pop()

										if len( self.is_on_else_define ) > 0:
											--self.else_define_level
											self.is_on_else_define.pop()

									if len( self.is_on_if_define ) > 0:
										--self.if_define_level
										self.is_on_if_define.pop()

									# If there are unclosed levels on the preprocessor, fix the `num_brace` level
									extra_levels = max( self.else_defined_brace_level, self.if_define_brace_level )
									num_brace   -= extra_levels

									# Both must to be equals, so just reset their levels.
									self.if_define_brace_level   -= extra_levels
									self.else_defined_brace_level -= extra_levels

					# Flags when we enter and leave the braces `{ ... }` blocks
					if c == '{':
						num_brace            += 1
						self.is_to_skip_brace = True

						if len( self.is_on_if_define ) > 0:

							if self.is_on_if_define[ -1 ] :
								self.if_define_brace_level += 1

							else:
								self.else_defined_brace_level += 1

					elif c == '}':
						pos        = i
						num_brace -= 1

						if len( self.is_on_if_define ) > 0:

							if self.is_on_if_define[ -1 ] :
								self.if_define_brace_level -= 1

							else:
								self.else_defined_brace_level -= 1
				#}

				penultimateChar = lastChar
				lastChar        = c
			#}

			# print_debug( 32, "num_brace:                %d" % num_brace )
			# print_debug( 32, "if_define_brace_level:    %d" % self.if_define_brace_level )
			# print_debug( 32, "else_defined_brace_level: %d" % self.else_defined_brace_level )

			# print_debug( 32, "is_on_if_define:          " + str( self.is_on_if_define ) )
			# print_debug( 32, "is_on_else_define:        " + str( self.is_on_else_define ) )
			# print_debug( 32, "" )

			if num_brace == 0 :
				self.restore_buffer = buffer[pos:]
				return

			buffer = self.read_line()
		#}
	#}

	def is_valid_name(self, name) :
	#{
		if not name or not name[0].isalpha() and name[0] != '_' :
			return False

		return re.match('^[\w_]+$', name) is not None
	#}

	def add_constant(self, name) :
	#{
		fixname = re.search('(\\w*)', name)

		if fixname :
			name = fixname.group(1)
			g_constants_list.add(name)
	#}

	def add_enum(self, buffer) :
	#{
		buffer = buffer.strip()
		if buffer == '' :
			return

		split = buffer.split('[')
		self.add_constant(split[0])

		self.add_general_autocomplete(buffer, 'enum', split[0])
		print_debug(8, "(analyzer) parse_enum add: [%s] -> [%s]" % (buffer, split[0]))
	#}

	def add_general_autocomplete(self, name, info, autocomplete) :
	#{
		self.node.func_words.append( name )

		if self.node.isFromBufferOnly or self.isTheCurrentFile:
			self.node.funcs.append( ["{}\t {}".format( name, info ), autocomplete] )
		else:
			self.node.funcs.append( ["{} \t{} - {}".format( name, self.file_name, info ), autocomplete] )
	#}

	def add_function_autocomplete(self, name, info, autocomplete, param_count) :
	#{
		show_name = name + "(" + str( param_count ) + ")"
		self.node.func_words.append( name )

		# We do not check whether `if name in func_words` because we can have several functions
		# with the same name but different parameters
		if self.node.isFromBufferOnly or self.isTheCurrentFile:
			self.node.funcs.append( ["{}\t {}".format( show_name, info ), autocomplete] )
		else:
			self.node.funcs.append( ["{} \t{} - {}".format( show_name, self.file_name, info ), autocomplete] )
	#}

	def add_word_autocomplete(self, name) :
		"""
			Used to add a word to the auto completion of the current buffer. Therefore, it does not
			need the file name as the auto completion for words from other files/sources.
		"""

		if name not in self.node.func_words:

			if self.isTheCurrentFile:
				self.node.funcs.append( [name, name] )
			else:
				self.node.funcs.append( ["{}\t - {}".format( name, self.file_name ), name] )

		self.node.func_words.append( name )

	def start_parse(self) :
	#{
		while True :
		#{
			buffer = self.read_line()
			# print_debug( 1, str( buffer ) )

			if buffer is None :
				break

			buffer = self.read_string(buffer)

			if len(buffer) <= 0 :
				continue

			#if "sma" in self.node.file_name :
			#	print("read: skip:[%d] brace_level:[%d] buff:[%s]" % (self.is_to_skip_next_line, self.brace_level, buffer))

			if self.is_to_skip_next_line :
				self.is_to_skip_next_line = False
				continue

			if buffer.startswith('#pragma deprecated') :
				buffer = self.read_line()
				if buffer is not None and buffer.startswith('stock ') :
					self.skip_function_block(buffer)
			elif buffer.startswith('#define ') :
				buffer = self.parse_define(buffer)
			elif buffer.startswith('const ') :
				buffer = self.parse_const(buffer)
			elif buffer.startswith('enum ') :
				self.found_enum = True
				self.enum_contents = ''
			elif buffer.startswith('new ') :
				self.parse_variable(buffer)
			elif buffer.startswith('public ') :
				self.parse_function(buffer, 1)
			elif buffer.startswith('stock ') :
				self.parse_function(buffer, 2)
			elif buffer.startswith('forward ') :
				self.parse_function(buffer, 3)
			elif buffer.startswith('native ') :
				self.parse_function(buffer, 4)
			elif not self.found_enum and not buffer[0] == '#' :
				self.parse_function(buffer, 0)

			if self.found_enum :
				self.parse_enum(buffer)
		#}
	#}

	def parse_define(self, buffer) :
	#{
		define = re.search('#define[\\s]+([^\\s]+)[\\s]+(.+)', buffer)

		if define :
		#{
			buffer = ''
			name   = define.group(1)
			value  = define.group(2).strip()

			count        = 0
			params       = name.split('(')
			name         = params[0]
			params_count = 0

			if len( params ) == 2:
				params       = params[1].split(',')
				comma_count  = len( params )
				params_count = comma_count

				# If we entered here, there are at least one parameter
				params = "${1:param1}"
				items  = range( 2, comma_count + 1 )

				for item in items:
					params += ", " + '${%d:param%d}' % ( item, item )
			else:
				params = ""

			if params_count > 0:
				self.add_function_autocomplete( name, 'define: ' + value, name + "(" + params + ")", params_count )
			else:
				self.add_general_autocomplete( name, 'define: ' + value, name )

			self.add_constant( name )
			print_debug(8, "(analyzer) parse_define add: [%s]" % name)
		#}
	#}

	def parse_const(self, buffer) :
	#{
		buffer = buffer[6:]

		split 	= buffer.split('=', 1)
		if len(split) < 2 :
			return

		name 	= split[0].strip()
		value 	= split[1].strip()

		newline = value.find(';')
		if (newline != -1) :
		#{
			self.restore_buffer = value[newline+1:].strip()
			value = value[0:newline]
		#}

		self.add_constant(name)
		self.add_general_autocomplete(name, 'const: ' + value, name)

		print_debug(8, "(analyzer) parse_const add: [%s]" % name)
	#}

	def parse_variable(self, buffer) :
	#{
		if buffer.startswith('new const ') :
			buffer = buffer[10:]
		else :
			buffer = buffer[4:]

		varName = ""
		lastChar = ''
		i = 0
		pos = 0
		num_brace = 0
		multiLines = True
		skipSpaces = False
		parseName = True
		inBrackets = False
		inBraces = False
		inString = False

		while multiLines :
		#{
			multiLines = False

			for c in buffer :
			#{
				i += 1

				if (c == '"') :
				#{
					if (inString and lastChar != '^') :
						inString = False
					else :
						inString = True
				#}

				if (inString == False) :
				#{
					if (c == '{') :
						num_brace += 1
						inBraces = True
					elif (c == '}') :
						num_brace -= 1
						if (num_brace == 0) :
							inBraces = False
				#}

				if skipSpaces :
				#{
					if c.isspace() :
						continue
					else :
						skipSpaces = False
						parseName = True
				#}

				if parseName :
				#{
					if (c == ':') :
						varName = ''
					elif (c == ' ' or c == '=' or c == ';' or c == ',') :
						varName = varName.strip()

						if (varName != '') :
							self.add_word_autocomplete( varName )
							print_debug(8, "(analyzer) parse_variable add: [%s]" % varName)

						varName = ''
						parseName = False
						inBrackets = False
					elif (c == '[') :
						inBrackets = True
					elif (inBrackets == False) :
						varName += c
				#}

				if (inString == False and inBrackets == False and inBraces == False) :
				#{
					if not parseName and c == ';' :
						self.restore_buffer = buffer[i:].strip()
						return

					if (c == ',') :
						skipSpaces = True
				#}

				lastChar = c
			#}

			if (c != ',') :
			#{
				varName = varName.strip()
				if varName != '' :
					self.add_word_autocomplete( varName )
					print_debug(8, "(analyzer) parse_variable add: [%s]" % varName)
			#}
			else :
			#{
				multiLines = True
				buffer = ' '

				while buffer is not None and buffer.isspace() :
					buffer = self.read_line()
			#}
		#}
	#}

	def parse_enum(self, buffer) :
	#{
		pos = buffer.find('}')
		if pos != -1 :
			buffer = buffer[0:pos]
			self.found_enum = False

		self.enum_contents = '%s\n%s' % (self.enum_contents, buffer)
		buffer = ''

		ignore = False
		if not self.found_enum :
		#{
			pos = self.enum_contents.find('{')
			self.enum_contents = self.enum_contents[pos + 1:]

			for c in self.enum_contents :
			#{
				if c == '=' or c == '#' :
					ignore = True
				elif c == '\n':
					ignore = False
				elif c == ':' :
					buffer = ''
					continue
				elif c == ',' :
					self.add_enum(buffer)
					buffer = ''

					ignore = False
					continue

				if not ignore :
					buffer += c
			#}

			self.add_enum(buffer)
			buffer = ''
		#}
	#}

	def parse_function(self, buffer, type) :
	#{
		multi_line = False
		temp = ''
		full_func_str = None
		open_paren_found = False

		while buffer is not None :
		#{

			buffer = buffer.strip()

			if not open_paren_found :
			#{
				parenpos = buffer.find('(')

				if parenpos == -1 :
					return

				open_paren_found = True
			#}
			if open_paren_found :
			#{
				pos = buffer.find(')')

				if pos != -1 :
					full_func_str = buffer[0:pos + 1]
					buffer = buffer[pos+1:]

					if (multi_line) :
						full_func_str = '%s%s' % (temp, full_func_str)

					break

				multi_line = True
				temp = '%s%s' % (temp, buffer)
			#}

			buffer = self.read_line()

			if buffer is None :
				return

			buffer = self.read_string(buffer)
		#}

		if full_func_str is not None :
		#{
			error = self.parse_function_params(full_func_str, type)

			if not error and type <= 2 :
				self.skip_function_block(buffer)

				if not self.is_to_skip_brace :
					self.is_to_skip_next_line = True

			#print("skip_brace: error:[%d] type:[%d] found:[%d] skip:[%d] func:[%s]" % (error, type, self.is_to_skip_brace, self.is_to_skip_next_line, full_func_str))
		#}
	#}

	def parse_function_params(self, func, type) :
	#{
		if type == 0 :
			remaining = func
		else :
			split = func.split(' ', 1)
			remaining = split[1]

		split = remaining.split('(', 1)

		if len(split) < 2 :
			print_debug(4, "(analyzer) parse_params return1: [%s]" % split)
			return 1

		remaining = split[1]
		returntype = ''
		funcname_and_return = split[0].strip()
		split_funcname_and_return = funcname_and_return.split(':')

		if len(split_funcname_and_return) > 1 :
			funcname = split_funcname_and_return[1].strip()
			returntype = split_funcname_and_return[0].strip()
		else :
			funcname = split_funcname_and_return[0].strip()

		if funcname.startswith("operator") :
			return 0

		if not self.is_valid_name(funcname) :
			print_debug(4, "(analyzer) parse_params invalid name: [%s]" % funcname)
			return 1

		remaining = remaining.strip()

		if remaining == ')':
			params = []

		else:
			params = remaining.strip()[:-1].split(',')

		if g_add_paremeters:
			i = 1
			autocomplete = funcname + '('

			for param in params:

				if i > 1:
					autocomplete += ', '

				autocomplete += '${%d:%s}' % (i, param.strip())
				i += 1

			autocomplete += ')'

		else:
			autocomplete = funcname + "()"

		self.add_function_autocomplete(funcname, FUNC_TYPES[type].lower(), autocomplete, len( params ))
		self.node.doct.add((funcname, func[func.find("(")+1:-1], self.node.file_name, type, returntype))

		print_debug(8, "(analyzer) parse_params add: [%s]" % func)
		return 0
	#}

#}

def process_buffer(text, node) :
#{
	if g_function_autocomplete:
		text_reader = TextReader(text)
		pawnParse.start(text_reader, node, True)
#}

def process_include_file(node) :
#{
	with open(node.file_name) as file :
		pawnParse.start(file, node)
#}

def simple_escape(html) :
#{
	return html.replace('&', '&amp;')
#}

EDITOR_VERSION = "3.0_zz"
FUNC_TYPES = [ "Function", "Public", "Stock", "Forward", "Native" ]

g_constants_list = set()
g_inteltip_style = ""
g_enable_inteltip = False
g_enable_buildversion = False
g_delay_time = 1.0
g_include_dir = "."
g_add_paremeters = False
g_new_file_syntax = "Packages/Amxmodx/AmxmodxPawn.sublime-syntax"
g_word_autocomplete = False
g_function_autocomplete = False

processingSetQueue = OrderedSetQueue()
processingSetQueue_set = set()
nodes = dict()
file_observer = watchdog.observers.Observer()
process_thread = ProcessQueueThread()
file_event_handler = IncludeFileEventHandler()
includes_re = re.compile('^[\\s]*#include[\\s]+[<"]([^>"]+)[>"]', re.MULTILINE)
local_re = re.compile('\\.(sma|inc)$')
pawnParse = PawnParse()

# limits to prevent bogging down the system
MIN_WORD_SIZE = 3
MAX_WORD_SIZE = 50

MAX_VIEWS = 20
MAX_WORDS_PER_VIEW = 100
MAX_FIX_TIME_SECS_PER_VIEW = 0.01

# Debugging
if 'LOG_FILE_NAME' in globals():
	del LOG_FILE_NAME

# LOG_FILE_NAME = os.path.abspath('AMXXEditor.log')
startTime = datetime.datetime.now()
print_debug_lastTime = startTime.microsecond

# Enable editor debug messages: (bitwise)
#
# 0  - Disabled debugging.
# 1  - Errors messages.
# 2  - Outputs when it starts a file parsing.
# 4  - General messages.
# 8  - Analyzer parser.
# 16 - Autocomplete debugging.
# 32 - Function parsing debugging.
# 63 - All debugging levels at the same time.
g_debug_level = 0

if 'LOG_FILE_NAME' in globals():

	# Clear the log file contents
	open(LOG_FILE_NAME, 'w').close()
	print( "Logging the AMXXEditor debug to the file " + LOG_FILE_NAME )

	# Setup the logger
	logging.basicConfig( filename=LOG_FILE_NAME, format='%(asctime)s %(message)s', level=logging.DEBUG )

	def print_debug(level, msg) :
	#{
		global print_debug_lastTime
		currentTime = datetime.datetime.now().microsecond

		# You can access global variables without the global keyword.
		if g_debug_level & level != 0:

			logging.debug( "[AMXX-Editor] " \
					+ str( currentTime ) \
					+ "%7d " % ( currentTime - print_debug_lastTime ) \
					+ msg )

			print_debug_lastTime = currentTime
	#}
else:

	def print_debug(level, msg) :
	#{
		global print_debug_lastTime
		currentTime = datetime.datetime.now().microsecond

		# You can access global variables without the global keyword.
		if g_debug_level & level != 0:

			print( "[AMXX-Editor] " \
					+ "%02d" % datetime.datetime.now().hour + ":" \
					+ "%02d" % datetime.datetime.now().minute + ":" \
					+ "%02d" % datetime.datetime.now().second + ":" \
					+ str( currentTime ) \
					+ "%7d " % ( currentTime - print_debug_lastTime ) \
					+ msg )

			print_debug_lastTime = currentTime
	#}


