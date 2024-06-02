scp -rp pi@192.168.1.201:/mnt/ssd/news_platform ./data
mv ./data/news_platform/* ./data/
rm -r ./data/news_platform
