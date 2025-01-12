# Amazon Linux 2023ベースのイメージを使用
FROM amazonlinux:2023

# 必要なツールをインストール
RUN yum install -y \
    python3 \
    python3-pip \
    zip \
    && python3 -m pip install --user --no-cache-dir --upgrade pip

# 環境変数の設定（ユーザーパスにインストールしたpipを利用）
ENV PATH=/root/.local/bin:$PATH

# 作業ディレクトリを設定
WORKDIR /var/task

# 必要なライブラリをインストール
RUN pip3 install --no-cache-dir pymupdf pillow -t ./python

# ZIPファイルを作成
RUN zip -r pdf_to_jpeg_layer.zip ./python
