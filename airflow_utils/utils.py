def file_download_progress(file_size, log=None):
    acc = 0

    def log_progress(chunk):
        nonlocal acc
        acc += chunk
        if log:
            log.info(f'Downloaded {(acc * 100 / file_size):.2f}% ({acc/1000000:.2f}/{file_size/1000000} MiB)')

    return log_progress