import unittest
from emulator import ShellEmulator
import os
import json
import shutil


class TestShellEmulator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Создаём копию vfs.zip для тестирования, чтобы не повредить основной архив
        shutil.copyfile('vfs.zip', 'vfs_test.zip')
        # Создаём config_test.toml
        with open('config_test.toml', 'w', encoding='utf-8') as f:
            f.write("""
username = "test_user"
hostname = "test_computer"
vfs_path = "vfs_test.zip"
log_path = "log.json"
startup_script = "startup.sh"
""")
    
    @classmethod
    def tearDownClass(cls):
        # Удаляем тестовый архив после всех тестов
        if os.path.exists('vfs_test.zip'):
            os.remove('vfs_test.zip')
        if os.path.exists('config_test.toml'):
            os.remove('config_test.toml')
        # Удаляем лог-файл
        if os.path.exists('log.json'):
            os.remove('log.json')

    def setUp(self):
        # Используем тестовый архив
        self.emulator = ShellEmulator('config_test.toml')

    def tearDown(self):
        # Очистка после каждого теста
        if hasattr(self, 'emulator') and self.emulator.vfs_path_extracted:
            self.emulator.cleanup()

    def test_startup_script_execution(self):
        """Проверка выполнения всего startup.sh"""
        self.emulator.cleanup()
        self.emulator = ShellEmulator('config_test.toml')

        # Проверяем лог
        with open('log.json', 'r', encoding='utf-8') as f:
            logs = json.load(f)

        expected_commands = [
            "ls",
            "cd home/user",
            "cp /file1.txt /home/user/documents/file2.txt",
            "head /home/user/documents/file2.txt"
        ]
        executed_commands = [log["action"] for log in logs]

        for command in expected_commands:
            self.assertIn(command, executed_commands)

        # Проверяем, что файл был скопирован
        self.assertIn('/home/user/documents/file2.txt', self.emulator.files)

        # Проверяем вывод команды head
        captured_output = []
        def mock_print(s):
            captured_output.append(s)
        original_print = __builtins__.print
        __builtins__.print = mock_print
        self.emulator.execute_command('head /home/user/documents/file2.txt')
        __builtins__.print = original_print

        # Проверяем, что head вывел первые 10 строк
        expected_head_output = [f"Line {i}" for i in range(1, 11)]
        self.assertEqual(captured_output, expected_head_output)

    def test_ls_command_root(self):
        """Проверка вывода команды ls в корневой директории"""
        self.emulator.current_path = '/'  # Reset the current directory to '/'
        captured_output = []
        def mock_print(s):
            captured_output.append(s)
        original_print = __builtins__.print
        __builtins__.print = mock_print
        self.emulator.execute_command('ls')
        __builtins__.print = original_print

        expected = {'home/', 'startup.sh', 'file1.txt'}
        self.assertEqual(set(captured_output), expected)

    def test_cd_command_success(self):
        """Проверка успешного перехода в существующую директорию"""
        self.emulator.execute_command('cd home/user')
        self.assertEqual(self.emulator.current_path, '/home/user')

    def test_cd_command_failure(self):
        """Проверка перехода в несуществующую директорию"""
        self.emulator.current_path = '/'  # Reset the current directory to '/'
        captured_output = []
        def mock_print(s):
            captured_output.append(s)
        original_print = __builtins__.print
        __builtins__.print = mock_print
        self.emulator.execute_command('cd /nonexistent')
        __builtins__.print = original_print
        self.assertEqual(self.emulator.current_path, '/')
        self.assertIn("cd: no such file or directory: /nonexistent", captured_output)

    def test_cp_command_success(self):
        """Проверка успешного копирования файла"""
        self.emulator.execute_command('cp /file1.txt /home/user/documents/file2.txt')
        self.assertIn('/home/user/documents/file2.txt', self.emulator.files)

    def test_head_command_success(self):
        """Проверка вывода первых 10 строк существующего файла"""
        self.emulator.execute_command('cp /file1.txt /home/user/documents/file2.txt')  # Сначала копируем файл
        captured_output = []
        def mock_print(s):
            captured_output.append(s)
        original_print = __builtins__.print
        __builtins__.print = mock_print
        self.emulator.execute_command('head /home/user/documents/file2.txt')
        __builtins__.print = original_print

        expected_head_output = [f"Line {i}" for i in range(1, 11)]
        self.assertEqual(captured_output, expected_head_output)

    def test_head_command_failure(self):
        """Проверка вывода для несуществующего файла"""
        captured_output = []
        def mock_print(s):
            captured_output.append(s)
        original_print = __builtins__.print
        __builtins__.print = mock_print
        self.emulator.execute_command('head /nofile.txt')
        __builtins__.print = original_print
        self.assertIn("head: cannot open '/nofile.txt': No such file or directory", captured_output)

    def test_clear_command(self):
        """Проверка выполнения команды clear"""
        # Эта команда просто очищает экран, поэтому проверяем, что она выполняется без ошибок
        self.emulator.execute_command('clear')

    def test_exit_command_log(self):
        """Проверка команды exit и записи в лог"""
        with self.assertRaises(SystemExit):
            self.emulator.execute_command('exit')
        with open('log.json', 'r', encoding='utf-8') as f:
            logs = json.load(f)
        self.assertIn("exit", logs[-1]['action'])


if __name__ == '__main__':
    unittest.main()