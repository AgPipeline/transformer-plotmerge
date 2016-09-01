#!/usr/bin/env python
import os
import subprocess
import logging
from config import *
import pyclowder.extractors as extractors


def main():
	global extractorName, messageType, rabbitmqExchange, rabbitmqURL

	# Set logging
	logging.basicConfig(format='%(levelname)-7s : %(name)s -  %(message)s', level=logging.WARN)
	logging.getLogger('pyclowder.extractors').setLevel(logging.INFO)

	# Connect to rabbitmq
	extractors.connect_message_bus(
		extractorName        = extractorName,
		messageType          = messageType,
		rabbitmqExchange     = rabbitmqExchange,
		rabbitmqURL          = rabbitmqURL,
		processFileFunction  = process_dataset,
		checkMessageFunction = check_message
	)

def check_message(parameters):
	# Check for expected input files before beginning processing
	if has_all_files(parameters):
		if has_output_file(parameters):
			print 'skipping, output file already exists'
			return False
		else:
			# Handle the message but do not download any files automatically.
			return "bypass"
	else:
		print 'skipping, not all input files are ready'
		return False

# ----------------------------------------------------------------------
# Process the dataset message and upload the results
def process_dataset(parameters):
	global extractorName, workerScript, inputDirectory, outputDirectory

	# Find input files in dataset
	files = get_all_files(parameters)

	# Download files to input directory
	for fileExt in files:
		files[fileExt]['path'] = extractors.download_file(
			channel            = parameters['channel'],
			header             = parameters['header'],
			host               = parameters['host'],
			key                = parameters['secretKey'],
			fileid             = files[fileExt]['id'],
			# What's this argument for?
			intermediatefileid = files[fileExt]['id'],
			ext                = fileExt
		)
		# Restore temp filenames to original - script requires specific name formatting so tmp names aren't suitable
		files[fileExt]['old_path'] = files[fileExt]['path']
		files[fileExt]['path'] = os.path.join(inputDirectory, files[fileExt]['filename'])
		os.rename(files[fileExt]['old_path'], files[fileExt]['path'])
		print 'found %s file: %s' % (fileExt, files[fileExt]['path'])

	# Invoke terraref.sh
	outFilePath = os.path.join(outputDirectory, get_output_filename(files['_raw']['filename']))
	print 'invoking terraref.sh to create: %s' % outFilePath
	subprocess.call(["bash", workerScript, "-d", "1", "-I", inputDirectory, "-O", outputDirectory])
	print 'done creating output file'

	# Verify outfile exists and upload to clowder
	if os.path.exists(outFilePath):
		print 'uploading output file...'
		extractors.upload_file_to_dataset(filepath=outFilePath, parameters=parameters)
		print 'done uploading'
	
	print 'cleaning up...'
	# Clean up the input files.
	for fileExt in files:
		os.remove(files[fileExt]['path'])
	# Clean up the output file.
	os.remove(outFilePath)
	print 'done cleaning'

# ----------------------------------------------------------------------
# Find as many expected files as possible and return the set.
def get_all_files(parameters):
	files = {
		'_raw': None,
		'_raw.hdr': None,
		'_image.jpg': None,
		'_metadata.json': None,
		'_frameIndex.txt': None,
		'_settings.txt': None
	}
	
	if 'filelist' in parameters:
		for fileItem in parameters['filelist']:
			fileId   = fileItem['id']
			fileName = fileItem['filename']
			for fileExt in files:
				if fileName[-len(fileExt):] == fileExt:
					files[fileExt] = {
						'id': fileId,
						'filename': fileName
					}
	return files

# ----------------------------------------------------------------------
# Returns the output filename.
def get_output_filename(raw_filename):
	return '%s.nc' % raw_filename[:-len('_raw')]

# ----------------------------------------------------------------------
# Returns true if all expected files are found.
def has_all_files(parameters):
	files = get_all_files(parameters)
	allFilesFound = True
	for fileExt in files:
		if files[fileExt] == None:
			allFilesFound = False
	return allFilesFound

# ----------------------------------------------------------------------
# Returns true if the output file is present.
def has_output_file(parameters):
	if 'filelist' not in parameters:
		return False
	if not has_all_files(parameters):
		return False
	files = get_all_files(parameters)
	outFilename = get_output_filename(files['_raw']['filename'])
	outFileFound = False
	for fileItem in parameters['filelist']:
		if outFilename == fileItem['filename']:
			outFileFound = True
			break
	return outFileFound

if __name__ == "__main__":
	main()