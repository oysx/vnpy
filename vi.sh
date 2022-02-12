sudo apt-get install gcc g++ python3-dev
function install_talib(){
    pushd /tmp
    wget https://pip.vnpy.com/colletion/ta-lib-0.4.0-src.tar.gz
    tar -xf ta-lib-0.4.0-src.tar.gz
    cd ta-lib
    ./configure
    make -j
    sudo make install
    popd
}

install_talib
pip install pip==21.1.1 setuptools==56.1.0 wheel==0.36.2
pip install -r vnpy.requirement.freeze.txt

