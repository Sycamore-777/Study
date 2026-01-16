## 使用说明
### ！！！注意！！！
### 文件中缺少private_key_b64.txt这个文件，里面存私钥，如有需求，联系Sycamore

1. 在目标机器上安装需要的docker
2. 注意挂载，参考下面的部署命令：
    ```bash
    docker run -it --name <your_container_name> -v /etc/machine-id:/host/etc/machine-id -v /sys/class/dmi/id:/host/sys/class/dmi/id:ro <your_image:tag> /bin/bash
    ```
    其余参数按需增加即可。
3. 在目标机器中的docker中的python环境中运行如下指令，获得fingerprint:
    ```python
    import encrypt_customer
    encrypt_customer.get_fingerprint()
    ```
4. 将fingerprint发送给发行方（所里）
5. 在发行方电脑的python环境中运行如下指令，获得license.lic
    ```python
    import encrypt_publisher
    # NOT_BEFORE_UTC和NOT_AFTER_UTC格式参考""
    # PRIVATE_KEY_B64：字符串，私钥，切勿外传，
    # APP_SECRET_B64 ：字符串，密钥
    # TARGET_FINGERPRINT_SHA256 # 字符串，目标机器的指纹，外部提供
    # NOT_BEFORE_UTC：字符串，授权开始时间，默认为"2026-01-13T00:00:00Z"
    # NOT_AFTER_UTC：字符串，授权终止时间，默认为"2027-01-13T00:00:00Z"
    # ISSUED_TO：字符串，目标用户ID，建议直接用大写字母简写
    # LICENSE_ID：字符串，license ID,建议使用"LIC-{YYYYMMDD}-ISSUED_TO-{xxx}",其中xxx表示三位序号，从001开始

    encrypt_publisher.create_license(
        private_key_b64=PRIVATE_KEY_B64,
        app_secret_b64=APP_SECRET_B64,target_fingerprint_sha256=TARGET_FINGERPRINT_SHA256,    not_before_utc=NOT_BEFORE_UTC,
        not_after_utc=NOT_AFTER_UTC,
        issued_to=ISSUED_TO,
        license_id=LICENSE_ID
        )
    ```
6. 在目标机器上重新挂载docker，增加license挂载：
    ```bash
    docker run -it --name <your_container_name> -v /etc/machine-id:/host/etc/machine-id -v /sys/class/dmi/id:/host/sys/class/dmi/id:ro -v <your_license.lic>:/app/license.lic <your_image:tag> /bin/bash
    ```
7. 在目标机器上的docker中的python中运行测试程序：
    ```python
    import encrypt_customer
    encrypt_customer.check_license()
    ```

### 其他
1.  如何将你自己的程序接入进来呢？
很简单，只需要将上一条的测试程序放在你的代码开头即可！  

2. 如何生成一对密钥呢？
执行以下程序即可：
    ```python
    import encrypt_publisher
    encrypt_publisher.create_keys() 
    ```

3. 公钥和派生密钥放在了customer中的license_guard.py中，使用时建议将程序封装后再发布。

4. publisher使用前也可以先运行一下如下代码进行初始化：
    ```python
    from publisher_init import publisher_init
    publisher_init()
    ```

