from __future__ import absolute_import
from __future__ import unicode_literals

import collections
import flask


# pylint:disable=star-args


Metric = collections.namedtuple('Metric', ['name', 'value', 'date'])


def get_metric_ids_from_database():
    result = flask.g.db.execute(
        'SELECT name FROM metric_names ORDER BY name'
    ).fetchall()
    return [name for name, in result]


def get_latest_sha():
    result = flask.g.db.execute(
        'SELECT sha FROM metric_data ORDER BY timestamp DESC LIMIT 1'
    ).fetchone()

    # If there is no data result will be None
    return result[0] if result else None


def get_sha_for_date(date):
    result = flask.g.db.execute(
        '\n'.join((
            'SELECT',
            '    sha',
            'FROM metric_data',
            'WHERE',
            '    timestamp <= ?',
            'ORDER BY timestamp DESC',
            'LIMIT 1',
        )),
        [date],
    ).fetchone()

    # If the date is too far in the past (before data) there won't be a result
    return result[0] if result else None


def get_metrics_for_sha(sha):
    # For no sha, we default all metrics to 0
    if not sha:
        return collections.defaultdict(int)

    result = flask.g.db.execute(
        '\n'.join((
            'SELECT',
            '    metric_names.name,',
            '    metric_data.running_value',
            'FROM metric_data',
            'INNER JOIN metric_names ON',
            '    metric_names.id = metric_data.metric_id',
            'WHERE',
            '    metric_data.sha = ?',
        )),
        [sha],
    ).fetchall()

    return dict(result)


def metrics_for_dates(metric_name, dates):
    def get_metric_for_timestamp(timestamp):
        result = flask.g.db.execute(
            '\n'.join((
                'SELECT',
                '    running_value,',
                '    timestamp',
                'FROM metric_data',
                'INNER JOIN metric_names ON',
                '    metric_names.id == metric_data.metric_id',
                'WHERE',
                '    metric_names.name == ? AND',
                '    timestamp < ?',
                'ORDER BY timestamp DESC',
                'LIMIT 1',
            )),
            [metric_name, timestamp],
        ).fetchone()
        if result:
            return Metric(metric_name, *result)
        else:
            return Metric(metric_name, 0, timestamp)

    return [get_metric_for_timestamp(date) for date in dates]


def get_first_data_timestamp(metric_name, db=None):
    db = db or flask.g.db
    result = db.execute(
        '\n'.join((
            'SELECT metric_data.timestamp',
            'FROM metric_data',
            'INNER JOIN metric_names ON'
            '    metric_names.id = metric_data.metric_id',
            'WHERE',
            '    metric_names.name = ? AND',
            '    metric_data.timestamp < (',
            '        SELECT metric_data.timestamp',
            '        FROM metric_data',
            '        INNER JOIN metric_names',
            '            ON metric_names.id = metric_data.metric_id',
            '        WHERE',
            '            metric_names.name = ? AND',
            '            metric_data.running_value > 0',
            '        ORDER BY metric_data.timestamp',
            '        LIMIT 1',
            '    )',
            'ORDER BY metric_data.timestamp DESC',
            'LIMIT 1',
        )),
        [metric_name, metric_name],
    ).fetchone()

    if result:
        return result[0]
    else:
        # Otherwise return the first timestamp in the db (or 0 for no data)
        return db.execute(
            '\n'.join((
                'SELECT',
                '    IFNULL(MIN(metric_data.timestamp), 0)',
                'FROM metric_data',
                'INNER JOIN metric_names ON',
                '    metric_names.id = metric_data.metric_id',
                'WHERE',
                '    metric_names.name = ?',
            )),
            [metric_name]
        ).fetchone()[0]


def get_all_data(metric_name, min_timestamp, max_timestamp, db=None):
    db = db or flask.g.db
    result = db.execute(
        '\n'.join((
            'SELECT',
            '    metric_data.sha,',
            '    metric_data.running_value,',
            '    metric_data.timestamp',
            'FROM metric_data',
            'INNER JOIN metric_names ON',
            '    metric_names.id == metric_data.metric_id',
            'WHERE',
            '    metric_names.name == ? AND',
            '    timestamp >= ? AND',
            '    timestamp < ?',
            'ORDER BY TIMESTAMP ASC',
        )),
        [metric_name, min_timestamp, max_timestamp],
    ).fetchall()

    return tuple(result)


def get_previous_sha(sha, db=None):
    db = db or flask.g.db

    # Attempt to find the sha of the commit directly before
    result = db.execute(
        '\n'.join((
            'SELECT',
            '    sha',
            'FROM metric_data',
            'WHERE',
            '    sha != ? AND',
            '    ROWID < (SELECT MAX(ROWID) FROM metric_data WHERE sha = ?)',
            'ORDER BY ROWID DESC',
            'LIMIT 1',
        )),
        [sha, sha],
    ).fetchone()

    # Possible that we are the first commit
    return result[0] if result else None


# TODO: this is duplicated, consolidate before shipping
def get_metric_values(sha, db=None):
    db = db or flask.g.db

    assert sha is not None

    return dict(db.execute(
        '\n'.join((
            'SELECT',
            '    metric_names.name,',
            '    running_value',
            'FROM metric_data',
            'INNER JOIN metric_names ON',
            '    metric_names.id = metric_data.metric_id',
            'WHERE sha = ?',
        )),
        [sha]
    ))
