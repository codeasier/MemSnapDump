from .adaptors.snapshot2memscope import dump

if __name__ == '__main__':
    dump('test-data/snapshot_expandable.pkl', 'test-data/leaks_dump_2222.db')
