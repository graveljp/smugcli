if [ "$1" == "--reset_cache" ]; then
    rm -rf $(dirname "$0")/testdata/request_cache
fi

python -m unittest discover -p "*_test.py"
