#!/usr/bin/env bash
# list the contents of the src directory
src_dir="build"
base_package_name="material-icons"
dist_file_path="src/init.luau"

# if directory "src" exists
if [ -d "src" ]; then
	# rename src to "build"
	mv src build
fi

# make a directory called dist if it doesn't exist
mkdir -p src

# for each file in the src directory check if it's not init.luau
for file in $src_dir/*; do
	if [ "$file" != "$src_dir/init.luau" ]; then
		# how many occurences of "{" there are in file
		brace_count=$(grep -o "{" $file | wc -l)
		# if brace_count > 300 then continue
		if [ $brace_count -lt 1322 ]; then
			echo "skipping $file, brace count is $brace_count"
			continue
		fi
		# assign the local path of file to file_path + src dir
		file_name=$(basename $file)

		# copy file over to dist directory at "dist/init.luau"
		cp $file $dist_file_path

		# remove extension from file_name
		package_suffix="${file_name%.*}"

		# replace _ with - in package_suffix
		package_suffix="${package_suffix//_/-}"

		# lowercase package_suffix
		package_suffix=$(echo $package_suffix | tr '[:upper:]' '[:lower:]')

		# replace the first occurence of "-" with "-dp" in package_suffix
		package_suffix="${package_suffix/-/-dp}"

		# add an "x" to the end
		package_suffix="${package_suffix}x"

		package_name="$base_package_name-$package_suffix"
		package_full_name="nightcycle/$package_name"
		echo "publishing as $package_name"

		# in wally.toml, change the line that startes with 'name =' with 'name = "$package_full_name"'
		sed -i "s#name = \".*\"#name = \"$package_full_name\"#" wally.toml
		
		# in default.project.json, change the line that icludes '"$path":' and replaces it with '"$path": "$file"'
		# sed -i "s#\"\$path\": \".*\"#\"\$path\": \"$dist_file_path\"#" default.project.json
		wally publish
	fi
done