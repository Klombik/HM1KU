import os
import zipfile
import json
import toml
import sys
from datetime import datetime
import shutil
import tempfile

class ShellEmulator:
    def __init__(self, config_path):
        self.load_config(config_path)
        self.load_vfs()
        self.current_path = '/'
        self.log = []
        self.run_startup_script()

    def load_config(self, config_path):
        with open(config_path, 'r') as f:
            config = toml.load(f)
        self.username = config['username']
        self.hostname = config['hostname']
        self.vfs_path = config['vfs_path']
        self.log_path = config['log_path']
        self.startup_script = config['startup_script']

    def load_vfs(self):
        if not os.path.isfile(self.vfs_path) or not zipfile.is_zipfile(self.vfs_path):
            print("Invalid VFS archive.")
            sys.exit(1)
        # Создайте временную директорию
        self.temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(self.vfs_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)
        self.vfs_path_extracted = self.temp_dir
        self.read_vfs()

    def read_vfs(self):
        # Обновляем список файлов и директорий после изменений
        self.files = []
        for root, dirs, files in os.walk(self.vfs_path_extracted):
            for dir in dirs:
                full_dir_path = os.path.join(root, dir)
                relative_path = os.path.relpath(full_dir_path, self.vfs_path_extracted)
                # Добавляем директории с завершающим слэшем
                self.files.append('/' + relative_path.replace(os.sep, '/') + '/')
            for file in files:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, self.vfs_path_extracted)
                self.files.append('/' + relative_path.replace(os.sep, '/'))

    def log_action(self, action):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user": self.username,
            "action": action
        }
        self.log.append(entry)
        with open(self.log_path, 'w') as f:
            json.dump(self.log, f, indent=4)

    def run_startup_script(self):
        script_full_path = os.path.join(self.vfs_path_extracted, self.startup_script)
        if os.path.isfile(script_full_path):
            with open(script_full_path, 'r') as f:
                commands = f.read().splitlines()
            for cmd in commands:
                self.execute_command(cmd)

    def prompt(self):
        return f"{self.username}@{self.hostname}:{self.current_path}$ "

    def list_dir(self, args):
        path = self.current_path if not args else args[0]
        normalized_path = self.normalize_path(path)
        if not normalized_path.endswith('/'):
            normalized_path += '/'
        contents = set()
        for f in self.files:
            if f.startswith(normalized_path):
                sub_path = f[len(normalized_path):].strip('/')
                if '/' in sub_path:
                    contents.add(sub_path.split('/')[0] + '/')
                elif sub_path:
                    # Проверяем, является ли элемент директорией
                    if f.endswith('/'):
                        contents.add(sub_path + '/')
                    else:
                        contents.add(sub_path)
        for item in sorted(contents):
            print(item)

    def change_dir(self, args):
        if not args:
            return
        new_path = args[0]
        if new_path == "..":
            if self.current_path != '/':
                self.current_path = os.path.dirname(self.current_path.rstrip('/')) or '/'
        else:
            potential_path = self.normalize_path(new_path)
            # Проверяем, существует ли директория
            if not potential_path.endswith('/'):
                potential_path += '/'
            if any(f == potential_path or f.startswith(potential_path) for f in self.files):
                self.current_path = potential_path.rstrip('/')
                if self.current_path == '':
                    self.current_path = '/'
            else:
                print(f"cd: no such file or directory: {new_path}")

    def copy_file(self, args):
        if len(args) != 2:
            print("cp: requires source and destination.")
            return
        src, dest = args
        src = self.normalize_path(src)
        dest = self.normalize_path(dest)
        full_src_path = self.get_full_path(src)
        full_dest_path = self.get_full_path(dest)
        
        if not os.path.exists(full_src_path):
            print(f"cp: cannot stat '{src}': No such file or directory")
            return
        if os.path.isdir(full_src_path):
            print(f"cp: omitting directory '{src}'")
            return
        os.makedirs(os.path.dirname(full_dest_path), exist_ok=True)
        shutil.copyfile(full_src_path, full_dest_path)
        self.read_vfs()  # Обновите список файлов после копирования

    def head_file(self, args):
        if not args:
            print("head: missing file operand.")
            return
        file = self.normalize_path(args[0])
        full_file_path = self.get_full_path(file)
        if not os.path.exists(full_file_path):
            print(f"head: cannot open '{args[0]}': No such file or directory")
            return
        try:
            with open(full_file_path, 'r') as f:
                for _ in range(10):
                    line = f.readline()
                    if not line:
                        break
                    print(line.rstrip())
        except Exception as e:
            print(f"head: error reading '{args[0]}': {e}")

    def clear_screen(self, args=None):
        os.system('cls' if os.name == 'nt' else 'clear')

    def normalize_path(self, path):
        if not path.startswith('/'):
            path = os.path.join(self.current_path, path)
        return os.path.normpath(path).replace('\\', '/')

    def get_full_path(self, path):
        if path.startswith('/'):
            return os.path.join(self.vfs_path_extracted, path.lstrip('/'))
        else:
            return os.path.join(self.vfs_path_extracted, self.current_path.lstrip('/'), path)

    def execute_command(self, command_line):
        if not command_line.strip():
            return
        parts = command_line.strip().split()
        cmd, args = parts[0], parts[1:]
        if cmd == 'ls':
            self.list_dir(args)
        elif cmd == 'cd':
            self.change_dir(args)
        elif cmd == 'exit':
            self.log_action("exit")
            self.cleanup()
            sys.exit(0)
        elif cmd == 'cp':
            self.copy_file(args)
        elif cmd == 'head':
            self.head_file(args)
        elif cmd == 'clear':
            self.clear_screen()
        else:
            print(f"{cmd}: command not found")
        self.log_action(command_line)

    def cleanup(self):
        # Упакуйте обратно в zip
        if os.path.exists(self.vfs_path_extracted):
            shutil.make_archive("vfs_updated", 'zip', self.vfs_path_extracted)
            # Переместите обновлённый архив на место оригинального
            shutil.move("vfs_updated.zip", self.vfs_path)
            # Удалите временную директорию
            shutil.rmtree(self.vfs_path_extracted)
            self.vfs_path_extracted = None
            
    def tearDown(self):
        # Очистка после каждого теста
        if hasattr(self, 'emulator') and self.emulator.vfs_path_extracted is not None:
            self.emulator.cleanup()

    def run(self):
        try:
            while True:
                command = input(self.prompt())
                self.execute_command(command)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting shell.")
            self.log_action("exit")
            self.cleanup()
            sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python emulator.py config.toml")
        sys.exit(1)
    emulator = ShellEmulator(sys.argv[1])
    emulator.run()