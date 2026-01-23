## 使用说明
### ！！！注意！！！
文件中缺少各类txt文件，如有需要联系Sycamore

### 在docker中使用

1. 在目标机器上安装需要的docker
2. 注意挂载，参考下面的部署命令：
    ```bash
    docker run -it --name <your_container_name> -v /etc/machine-id:/host/etc/machine-id -v /sys/class/dmi/id:/host/sys/class/dmi/id:ro <your_image:tag> /bin/bash
    ```
    其余参数按需增加即可。
3. 在目标机器中的docker中的python环境中运行如下指令，获得fingerprint:
    ```python
    # 如果你使用的是源代码
    import license_guard
    license_guard.build_expected_fingerprint()
    # 如果你使用的是setup出来的动态链接库
    import encrypt_customer_pkg
    encrypt_customer_pkg.get_fingerprint()
    ```
4. 将fingerprint发送给发行方
5. 在发行方电脑的python环境中运行如下指令，获得license.lic
    ```python
    # PRIVATE_KEY_B64：字符串，私钥，切勿外传，
    # master_key_b64 ：字符串，密钥，请勿外传
    # TARGET_FINGERPRINT_SHA256 ：字符串，目标机器的指纹，外部提供
    # FINGERPRINT_SOURCE：目标运行环境，如果在window/linux本机上使用native;linux 宿主机的docker上使用docker-host-mount;windows宿主机的docker上使用host-attest
    # ISSUED_TO：字符串，目标用户ID，建议直接用大写字母简写
    # LICENSE_ID：字符串，license ID,建议使用"LIC-{YYYYMMDD}-ISSUED_TO-{xxx}",其中xxx表示三位序号，从001开始
    # NOT_BEFORE_UTC：字符串，授权开始时间，默认为"2026-01-13T00:00:00Z"
    # NOT_AFTER_UTC：字符串，授权终止时间，默认为"2027-01-13T00:00:00Z"

    # 如果你使用的是源代码
    import issue_license
    issue_license.create_write_lic(
        private_key_b64=PRIVATE_KEY_B64,
        master_key_b64=MASTER_KEY_B64,
        target_fingerprint_sha256=TARGET_FINGERPRINT_SHA256,
        fingerprint_source=FINGERPRINT_SOURCE,
        issued_to=ISSUED_TO,
        license_id=LICENSE_ID,
        not_before_utc=NOT_BEFORE_UTC,
        not_after_utc=NOT_AFTER_UTC,
    )

    # 如果你使用的是setup出来的动态链接库
    import encrypt_publisher_pkg
    encrypt_publisher_pkg.create_license(
        private_key_b64=PRIVATE_KEY_B64,
        master_key_b64=MASTER_KEY_B64,
        target_fingerprint_sha256=TARGET_FINGERPRINT_SHA256,
        fingerprint_source=FINGERPRINT_SOURCE,
        issued_to=ISSUED_TO,
        license_id=LICENSE_ID,
        not_before_utc=NOT_BEFORE_UTC,
        not_after_utc=NOT_AFTER_UTC,
    )
    ```
6. 在目标机器上重新挂载docker，增加license挂载：
    ```bash
    docker run -it --name <your_container_name> -v /etc/machine-id:/host/etc/machine-id -v /sys/class/dmi/id:/host/sys/class/dmi/id:ro -v <your_license.lic>:/app/license.lic <your_image:tag> /bin/bash
    ```
7. 在目标机器上的docker中的python中运行测试程序：
    ```python
    # issuer_public_key_b64：公钥，
    # license_master_key_b64 ：密钥
    # app_secret_b64：密钥，与license_master_key_b64一致
    # license_path：license路径 XXX/license.lic,注意与你挂载或者本机存放地方一致即可
    
    # 如果你使用的是源代码
    import license_guard
    license_guard.check_license(
        issuer_public_key_b64=issuer_public_key_b64,
        license_master_key_b64=license_master_key_b64,
        app_secret_b64=app_secret_b64,
        license_path=license_path,
    )
    # 如果你使用的是setup出来的动态链接库
    import encrypt_customer_pkg
    encrypt_customer_pkg.check_license(
        issuer_public_key_b64=issuer_public_key_b64,
        license_master_key_b64=license_master_key_b64,
        app_secret_b64=app_secret_b64,
        license_path=license_path
    )
    ```

### 在本机（windows/linux）中使用

1. 在目标机器中的python环境中运行如下指令，获得fingerprint:
    ```python
    # 如果你使用的是源代码
    import license_guard
    license_guard.build_expected_fingerprint()
    # 如果你使用的是setup出来的动态链接库
    import encrypt_customer_pkg
    encrypt_customer_pkg.get_fingerprint()
    ```
2. 将fingerprint发送给发行方
3. 在发行方电脑的python环境中运行如下指令，获得license.lic
    ```python

    # PRIVATE_KEY_B64：字符串，私钥，切勿外传，
    # master_key_b64 ：字符串，密钥，请勿外传
    # TARGET_FINGERPRINT_SHA256 ：字符串，目标机器的指纹，外部提供
    # FINGERPRINT_SOURCE：目标运行环境，如果在window/linux本机上使用native;linux 宿主机的docker上使用docker-host-mount;windows宿主机的docker上使用host-attest
    # ISSUED_TO：字符串，目标用户ID，建议直接用大写字母简写
    # LICENSE_ID：字符串，license ID,建议使用"LIC-{YYYYMMDD}-ISSUED_TO-{xxx}",其中xxx表示三位序号，从001开始
    # NOT_BEFORE_UTC：字符串，授权开始时间，默认为"2026-01-13T00:00:00Z"
    # NOT_AFTER_UTC：字符串，授权终止时间，默认为"2027-01-13T00:00:00Z"

    # 如果你使用的是源代码
    import issue_license
    issue_license.create_write_lic(
        private_key_b64=PRIVATE_KEY_B64,
        master_key_b64=MASTER_KEY_B64,
        target_fingerprint_sha256=TARGET_FINGERPRINT_SHA256,
        fingerprint_source=FINGERPRINT_SOURCE,
        issued_to=ISSUED_TO,
        license_id=LICENSE_ID,
        not_before_utc=NOT_BEFORE_UTC,
        not_after_utc=NOT_AFTER_UTC,
    )

    # 如果你使用的是setup出来的动态链接库
    import encrypt_publisher_pkg
    encrypt_publisher_pkg.create_license(
        private_key_b64=PRIVATE_KEY_B64,
        master_key_b64=MASTER_KEY_B64,
        target_fingerprint_sha256=TARGET_FINGERPRINT_SHA256,
        fingerprint_source=FINGERPRINT_SOURCE,
        issued_to=ISSUED_TO,
        license_id=LICENSE_ID,
        not_before_utc=NOT_BEFORE_UTC,
        not_after_utc=NOT_AFTER_UTC,
    )
    ```
4. 在目标机器上的python中运行测试程序：
    ```python
    # issuer_public_key_b64：公钥，
    # license_master_key_b64 ：密钥
    # app_secret_b64：密钥，与license_master_key_b64一致
    # license_path：license路径 XXX/license.lic,注意与你挂载或者本机存放地方一致即可
    
    # 如果你使用的是源代码
    import license_guard
    license_guard.check_license(
        issuer_public_key_b64=issuer_public_key_b64,
        license_master_key_b64=license_master_key_b64,
        app_secret_b64=app_secret_b64,
        license_path=license_path,
    )
    # 如果你使用的是setup出来的动态链接库
    import encrypt_customer_pkg
    encrypt_customer_pkg.check_license(
        issuer_public_key_b64=issuer_public_key_b64,
        license_master_key_b64=license_master_key_b64,
        app_secret_b64=app_secret_b64,
        license_path=license_path
    )
    ```

### 其他
1.  如何将你自己的程序接入进来呢？
很简单，只需要将上一条的测试程序放在你的代码开头即可！  

2. 如何生成一对密钥呢？
执行以下程序即可：
    ```python
    import encrypt_publisher_pkg
    encrypt_publisher_pkg.create_keys() 
    ```

3. publisher使用前也可以先运行一下如下代码进行初始化：
    ```python
    # 如果你使用的是源代码
    from publisher_init import publisher_init
    publisher_init()

    # 如果你使用的是源代码
    import encrypt_publisher_pkg
    encrypt_publisher_pkg.init_publisher()
    ```

